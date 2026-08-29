"""
Management command to compute and persist StatusBottleneckMetrics snapshots (Postgres-optimized).

This implementation:
 - Uses a single calculated_at timestamp per run and writes all rows for that run
   with the same calculated_at (avoids mixed-timestamp snapshots).
 - Aggregates IssueStatusChange rows in the database per status_id using GROUP BY,
   computing distinct issue counts and average time-in-status (in days) via EXTRACT(EPOCH FROM ...).
 - Ensures a row is generated for every IssueStatus for each (period, region, category)
   combination processed. Non-terminal statuses with no data will have issues_count=0
   and average_time_in_status_days=None (or 0.0 if the model disallows NULL).
 - Persists rows in bulk for performance.
 - If run without --period, computes snapshots for all supported periods (7d, 30d, 90d).
 - When explicit --regions or --categories are provided, only those ids are processed (no implicit global None).
 - Always creates snapshots for administrative_region=None and category=None when the command is invoked without explicit region/category filters or when --only-global is used.
"""

from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import (
    Avg,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    Func,
    Q,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from dashboard.constants import MONTHLY_CHOICE, QUARTERLY_CHOICE, WEEKLY_CHOICE
from dashboard.models import StatusBottleneckMetrics
from issues.models import (
    AdministrativeRegion,
    Issue,
    IssueCategory,
    IssueStatus,
    IssueStatusChange,
)

LOCK_KEY = "populate_status_bottlenecks_lock_v2"
LOCK_TIMEOUT = 60 * 60 * 3  # 3 hours


def _period_to_window(period):
    end_date = timezone.now()
    if period == MONTHLY_CHOICE:
        start_date = end_date - timedelta(days=30)
    elif period == QUARTERLY_CHOICE:
        start_date = end_date - timedelta(days=90)
    else:
        start_date = end_date - timedelta(days=7)
    return start_date, end_date


def _chunked_iterable(iterable, chunk_size):
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


class ExtractEpoch(Func):
    """
    Helper Func to produce EXTRACT(EPOCH FROM <field>) in SQL.
    Usage: ExtractEpoch(F('exited_at'))
    """

    function = 'EXTRACT'
    template = "EXTRACT(EPOCH FROM %(expressions)s)"


class Command(BaseCommand):
    help = "Compute and persist StatusBottleneckMetrics snapshots (Postgres-optimized)."

    def add_arguments(self, parser):
        # default=None so we can detect "no --period provided" and run all periods
        parser.add_argument(
            '--period', default=None, help="Period to compute (7d, 30d, 90d). If omitted, all periods will be computed."
        )
        parser.add_argument('--regions', nargs='*', type=int, help="List of administrative region ids to process")
        parser.add_argument('--categories', nargs='*', type=int, help="List of category ids to process")
        parser.add_argument('--limit-regions', type=int, default=None, help="Limit number of regions to process")
        parser.add_argument('--limit-categories', type=int, default=None, help="Limit number of categories to process")
        parser.add_argument('--batch-size', type=int, default=10, help="Batch size for processing regions (default 10)")
        parser.add_argument('--dry-run', action='store_true', help="Do not persist results, only simulate")
        parser.add_argument(
            '--only-global', action='store_true', help="Only compute the global (no region, no category) snapshot"
        )
        parser.add_argument(
            '--start-date', type=str, default=None, help="Optional ISO start datetime (overrides period)"
        )
        parser.add_argument('--end-date', type=str, default=None, help="Optional ISO end datetime (overrides period)")
        parser.add_argument(
            '--no-lock', action='store_true', help="Disable the cache-based lock (useful for local testing)"
        )
        parser.add_argument(
            '--calculated-at',
            type=str,
            default=None,
            help="Optional ISO datetime to use as calculated_at for the snapshot (overrides default timezone.now()).",
        )
        parser.add_argument(
            '--include-open-durations',
            action='store_true',
            help="Include open IssueStatusChange rows in average by using end_date as exited_at (default: exclude open rows).",
        )

    def handle(self, *args, **options):
        # Accept either a single period or None (meaning all periods)
        requested_period = options['period']
        region_ids = options.get('regions') or []
        category_ids = options.get('categories') or []
        limit_regions = options.get('limit_regions')
        limit_categories = options.get('limit_categories')
        batch_size = options.get('batch_size') or 10
        dry_run = options.get('dry_run', False)
        only_global = options.get('only_global', False)
        start_date_opt = options.get('start_date')
        end_date_opt = options.get('end_date')
        no_lock = options.get('no_lock', False)
        calculated_at_opt = options.get('calculated_at')
        include_open = options.get('include_open_durations', False)

        # Acquire a simple cache lock to avoid concurrent runs
        if not no_lock:
            acquired = cache.add(LOCK_KEY, "1", LOCK_TIMEOUT)
            if not acquired:
                raise CommandError("Another populate_status_bottlenecks run appears to be active. Aborting.")
            self.stdout.write(self.style.NOTICE("Acquired run lock."))

        # Use a single calculated_at timestamp for the whole command run (can be overridden)
        if calculated_at_opt:
            parsed = parse_datetime(calculated_at_opt)
            if parsed is None:
                raise CommandError(f"Invalid --calculated-at datetime: {calculated_at_opt}")
            if timezone.is_naive(parsed):
                calculated_at = timezone.make_aware(parsed, timezone=timezone.utc)
            else:
                calculated_at = parsed
        else:
            calculated_at = timezone.now()

        self.stdout.write(self.style.SUCCESS(f"Snapshot calculated_at will be: {calculated_at.isoformat()}"))

        try:
            # Parse optional explicit start/end overrides (apply to all periods if provided)
            if start_date_opt:
                start_date_override = parse_datetime(start_date_opt) or (
                    parse_date(start_date_opt)
                    and timezone.make_aware(
                        timezone.datetime.combine(parse_date(start_date_opt), timezone.datetime.min.time())
                    )
                )
            else:
                start_date_override = None

            if end_date_opt:
                end_date_override = parse_datetime(end_date_opt) or (
                    parse_date(end_date_opt)
                    and timezone.make_aware(
                        timezone.datetime.combine(parse_date(end_date_opt), timezone.datetime.max.time())
                    )
                )
            else:
                end_date_override = None

            # Determine which periods to process
            if requested_period:
                # validate requested_period against known choices; fallback to weekly if invalid
                valid_periods = {WEEKLY_CHOICE, MONTHLY_CHOICE, QUARTERLY_CHOICE}
                if requested_period not in valid_periods:
                    self.stdout.write(
                        self.style.WARNING(f"Unknown period '{requested_period}', falling back to {WEEKLY_CHOICE}")
                    )
                    periods = [WEEKLY_CHOICE]
                else:
                    periods = [requested_period]
            else:
                # No --period provided: compute for all supported periods
                periods = [WEEKLY_CHOICE, MONTHLY_CHOICE, QUARTERLY_CHOICE]

            self.stdout.write(self.style.SUCCESS(f"Will compute snapshots for periods: {', '.join(periods)}"))
            self.stdout.write(self.style.SUCCESS(f"Snapshot calculated_at will be: {calculated_at.isoformat()}"))

            # Build region list based on regions that have confirmed issues, and include ancestors
            parent_map = {r['id']: r['parent_id'] for r in AdministrativeRegion.objects.values('id', 'parent_id')}

            def build_ancestor_ids_in_memory(start_id):
                ids = [start_id]
                parent_id = parent_map.get(start_id)
                while parent_id:
                    ids.append(parent_id)
                    parent_id = parent_map.get(parent_id)
                return ids[::-1]  # root -> ... -> start_id

            region_ids_with_issues = (
                AdministrativeRegion.objects.filter(issues__confirmed=True).values_list('id', flat=True).distinct()
            )

            regions_to_process_ids = set()
            for rid in region_ids_with_issues:
                regions_to_process_ids.update(build_ancestor_ids_in_memory(rid))

            regions_qs = AdministrativeRegion.objects.filter(id__in=list(regions_to_process_ids)).order_by('id')

            # Apply explicit region_ids filter if provided (intersection)
            if region_ids:
                regions_qs = regions_qs.filter(id__in=region_ids)

            if limit_regions:
                regions_qs = regions_qs[:limit_regions]

            regions = list(regions_qs)
            self.stdout.write(self.style.SUCCESS(f"Regions to process: {len(regions)}"))

            # Build category queryset/list (only categories are fine; we keep all categories or limit)
            if category_ids:
                categories_qs = IssueCategory.objects.filter(id__in=category_ids).order_by('id')
            else:
                categories_qs = IssueCategory.objects.all().order_by('id')
                if limit_categories:
                    categories_qs = categories_qs[:limit_categories]

            categories = list(categories_qs)
            self.stdout.write(self.style.SUCCESS(f"Categories to process: {len(categories)}"))

            # If only_global, compute only the global snapshot(s)
            if only_global:
                self.stdout.write("Processing global snapshot(s) only.")
                for period in periods:
                    if start_date_override or end_date_override:
                        start_date = start_date_override
                        end_date = end_date_override
                    else:
                        start_date, end_date = _period_to_window(period)

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Using window for period {period}: {start_date.isoformat()} -> {end_date.isoformat()}"
                        )
                    )

                    if dry_run:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Dry-run: would compute snapshot for global (period={period}, start={start_date}, end={end_date})"
                            )
                        )
                    else:
                        self._compute_and_persist_snapshot(
                            period,
                            start_date,
                            end_date,
                            region=None,
                            category=None,
                            calculated_at=calculated_at,
                            include_open=include_open,
                        )
                return

            # Process in batches over regions to avoid long single transactions
            total_tasks = 0
            for period in periods:
                # determine window for this period (unless overrides provided)
                if start_date_override or end_date_override:
                    start_date = start_date_override
                    end_date = end_date_override
                else:
                    start_date, end_date = _period_to_window(period)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Processing period {period} with window: {start_date.isoformat()} -> {end_date.isoformat()}"
                    )
                )

                # Build iterables for regions and categories.
                # Important: if the caller passed explicit --regions or --categories, respect those and do NOT implicitly include None.
                actual_regions = regions or []
                actual_categories = categories or []

                # Regions iterable: if explicit region_ids were provided, process only those regions (no implicit None).
                if region_ids:
                    # chunk the explicit regions for batching
                    if actual_regions:
                        regions_iterable_chunks = list(_chunked_iterable(actual_regions, batch_size))
                    else:
                        regions_iterable_chunks = []
                else:
                    # caller did not pass explicit regions -> include global None in first chunk
                    if actual_regions:
                        region_chunks = list(_chunked_iterable(actual_regions, batch_size))
                        if region_chunks:
                            region_chunks[0] = [None] + region_chunks[0]
                        else:
                            region_chunks = [[None]]
                    else:
                        region_chunks = [[None]]
                    regions_iterable_chunks = region_chunks

                # Categories iterable: include None only when caller did not pass explicit category ids
                if category_ids:
                    categories_iterable = actual_categories
                else:
                    categories_iterable = [None] + actual_categories

                # If both region_ids and category_ids were provided but one of them is empty (no matches),
                # ensure we still iterate at least once to allow processing of the other dimension.
                if not regions_iterable_chunks:
                    # If explicit regions were requested but none matched (edge case), skip region processing.
                    regions_iterable_chunks = []

                # Iterate chunks and process combinations
                for region_chunk in regions_iterable_chunks:
                    for region in region_chunk:
                        for category in categories_iterable:
                            total_tasks += 1
                            region_desc = f"region={region.id}" if region else "region=None"
                            category_desc = f"category={category.id}" if category else "category=None"
                            self.stdout.write(f"Task #{total_tasks}: period={period}, {region_desc}, {category_desc}")

                            if dry_run:
                                self.stdout.write(
                                    self.style.WARNING("Dry-run: skipping persist call (would compute snapshot)")
                                )
                                continue

                            try:
                                self._compute_and_persist_snapshot(
                                    period,
                                    start_date,
                                    end_date,
                                    region=region,
                                    category=category,
                                    calculated_at=calculated_at,
                                    include_open=include_open,
                                )
                            except Exception as exc:
                                self.stderr.write(
                                    self.style.ERROR(
                                        f"Error persisting for {region_desc}, {category_desc}, period={period}: {exc}"
                                    )
                                )
                                continue

            self.stdout.write(self.style.SUCCESS(f"Completed processing {total_tasks} tasks."))

        finally:
            if not no_lock:
                cache.delete(LOCK_KEY)
                self.stdout.write(self.style.NOTICE("Released run lock."))

    def _compute_and_persist_snapshot(
        self, period, start_date, end_date, region=None, category=None, calculated_at=None, include_open=None
    ):
        """
        Compute and persist StatusBottleneckMetrics for one (period, start_date, end_date, region, category).

        Performs DB-side aggregation and writes one row per IssueStatus with the same
        calculated_at timestamp.

        Parameters
        ----------
        period : str
            Period identifier (e.g. "7d", "30d", "90d").
        start_date, end_date : datetime
            Window used to select IssueStatusChange.entered_at.
        region : AdministrativeRegion or None
            If provided, include issues in this region and its descendants; None means global (administrative_region IS NULL).
        category : IssueCategory or None
            If provided, filter by issue category; None means global (category IS NULL).
        calculated_at : datetime or None
            Timestamp to assign to created rows. If None, timezone.now() is used.
        include_open : bool or None
            If True, treat exited_at IS NULL as exited_at = end_date (open rows contribute to durations).
            If False/None, exclude open rows from the AVG (only closed durations are averaged).

        Behavior
        --------
        - Builds a base IssueStatusChange queryset for entered_at in [start_date, end_date] and issue__confirmed=True.
        - Applies region/category filters only when region/category are not None.
        - Computes per-status:
            - issues_count = COUNT(DISTINCT issue_id)
            - average_time_in_status_days = AVG(duration_seconds) / 86400.0 (NULL if no closed rows)
          If the model disallows NULL for average_time_in_status_days, stores 0.0 when no value exists.
        - For terminal statuses (final/rejected) avg is considered not applicable; issues_count is computed from Issue table.
        - Persists rows in a transaction: deletes any existing rows for the same (period, calculated_at, administrative_region, category) and bulk_creates the new set.

        Notes
        -----
        - include_open changes the meaning of the average (partial durations vs only closed durations). Choose and apply consistently.
        - This function is optimized for Postgres and intended to be run per shard (region/category) rather than one huge transaction.
        """

        self.stdout.write(
            self.style.NOTICE(
                f"Computing snapshot: period={period}, region={'None' if not region else region.id}, category={'None' if not category else category.id}, start={start_date.isoformat()}, end={end_date.isoformat()}"
            )
        )

        if calculated_at is None:
            calculated_at = timezone.now()

        # Build region/category filters for Issue and IssueStatusChange
        region_filter_issue = Q()
        if region:
            try:
                descendant_ids = region.get_descendant_ids()
                region_filter_issue = Q(administrative_region_id__in=descendant_ids)
                region_filter_isc = Q(issue__administrative_region_id__in=descendant_ids)
            except Exception:
                region_filter_issue = Q(administrative_region=region)
                region_filter_isc = Q(issue__administrative_region=region)
        else:
            region_filter_issue = Q()
            region_filter_isc = Q()

        category_filter_issue = Q()
        if category:
            category_filter_issue = Q(category=category)
            category_filter_isc = Q(issue__category=category)
        else:
            category_filter_issue = Q()
            category_filter_isc = Q()

        statuses = list(IssueStatus.objects.order_by('id'))

        # Base ISC queryset for the window and confirmed issues
        isc_base_qs = IssueStatusChange.objects.filter(
            entered_at__gte=start_date, entered_at__lte=end_date, issue__confirmed=True
        )

        # Apply region/category filters only when they are meaningful (avoid .filter(Q()) no-op)
        if region is not None:
            # region_filter_isc was built earlier; apply it explicitly
            isc_base_qs = isc_base_qs.filter(region_filter_isc)
        if category is not None:
            isc_base_qs = isc_base_qs.filter(category_filter_isc)

        # If include_open is True, treat exited_at NULL as end_date for duration calculation
        if include_open:
            # Use COALESCE(exited_at, end_date) so open rows contribute with (end_date - entered_at)
            exited_expr = Coalesce(F('exited_at'), Value(end_date))
            exited_epoch = ExtractEpoch(exited_expr)
        else:
            exited_epoch = ExtractEpoch(F('exited_at'))

        entered_epoch = ExtractEpoch(F('entered_at'))
        seconds_diff_expr = ExpressionWrapper(exited_epoch - entered_epoch, output_field=FloatField())

        # Aggregate per status in DB: distinct issue count and average seconds (only rows with exited_at not null contribute to avg)
        per_status_agg = isc_base_qs.values('status_id').annotate(
            issues_count=Count('issue_id', distinct=True),
            avg_seconds=Avg(
                ExpressionWrapper(
                    # Only compute seconds where exited_at is not null; DB will ignore nulls in AVG
                    seconds_diff_expr,
                    output_field=FloatField(),
                )
            ),
        )

        # Build a map status_id -> aggregation dict
        agg_map = {p['status_id']: p for p in per_status_agg}

        rows_to_create = []

        # Helper to compute issues_count for terminal statuses from Issue table (fast DB count)
        def _count_confirmed_issues_for_status(status_obj):
            qs = Issue.objects.filter(confirmed=True, status=status_obj)
            if region_filter_issue:
                qs = qs.filter(region_filter_issue)
            if category_filter_issue:
                qs = qs.filter(category_filter_issue)
            return qs.count()

        # Inspect model field nullability for average_time_in_status_days
        avg_field = StatusBottleneckMetrics._meta.get_field('average_time_in_status_days')
        avg_allows_null = getattr(avg_field, 'null', False)

        # --- Fetch previous snapshot averages per status for this (period, region, category) if any ---
        # We want the latest existing snapshot per issue_status (calculated_at < current calculated_at).
        prev_avg_map = {}
        prev_qs = (
            StatusBottleneckMetrics.objects.filter(
                period=period, administrative_region=region, category=category, calculated_at__lt=calculated_at
            )
            .order_by('issue_status_id', '-calculated_at')
            .distinct('issue_status_id')
            .values('issue_status_id', 'average_time_in_status_days')
        )
        for r in prev_qs:
            prev_avg_map[r['issue_status_id']] = r['average_time_in_status_days']

        # Build model instances for all statuses
        for status in statuses:
            agg = agg_map.get(status.id)
            if agg:
                issues_count = agg.get('issues_count') or 0
                avg_seconds = agg.get('avg_seconds')
                # For terminal statuses we prefer to store "no avg"
                if status.final_status or status.rejected_status:
                    avg_days_raw = None
                else:
                    avg_days_raw = (float(avg_seconds) / 86400.0) if avg_seconds is not None else None
            else:
                if status.final_status or status.rejected_status:
                    issues_count = _count_confirmed_issues_for_status(status)
                    avg_days_raw = None
                else:
                    issues_count = 0
                    avg_days_raw = None

            # Choose stored value: if model disallows NULL, store 0.0 instead of None
            if avg_days_raw is None and not avg_allows_null:
                avg_days_to_store = 0.0
            else:
                avg_days_to_store = avg_days_raw

            # Explicit instantiation using the model's actual field name for the percentage
            row = StatusBottleneckMetrics(
                period=period,
                start_date=start_date,
                end_date=end_date,
                issues_count=issues_count,
                average_time_in_status_days=avg_days_to_store,
                calculated_at=calculated_at,
                administrative_region=region,
                category=category,
                issue_status=status,
            )
            rows_to_create.append(row)

        # Persist rows in a single transaction for this (period, region, category)
        with transaction.atomic():
            # Remove any rows that would conflict for the same (period, calculated_at, administrative_region, category)
            StatusBottleneckMetrics.objects.filter(
                period=period, calculated_at=calculated_at, administrative_region=region, category=category
            ).delete()

            if rows_to_create:
                StatusBottleneckMetrics.objects.bulk_create(rows_to_create, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f"Persisted snapshot for period={period}, region={'None' if not region else region.id}, category={'None' if not category else category.id} "
                f"calculated_at={calculated_at.isoformat()} rows={len(rows_to_create)}"
            )
        )
