from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from dashboard.constants import MONTHLY_CHOICE, QUARTERLY_CHOICE, WEEKLY_CHOICE
from dashboard.models import RegionPerformanceMetrics
from issues.models import AdministrativeRegion, IssueCategory


class Command(BaseCommand):
    help = "Populate RegionPerformanceMetrics for administrative levels."

    def add_arguments(self, parser):
        parser.add_argument(
            '--periods',
            nargs='+',
            type=str,
            default=[WEEKLY_CHOICE, MONTHLY_CHOICE, QUARTERLY_CHOICE],
            help="Periods to calculate (default: 7d 30d 90d)",
        )
        parser.add_argument('--regions', nargs='+', type=int, help="Specific region IDs to process (start set).")
        parser.add_argument(
            '--categories', nargs='+', type=int, help="Specific category IDs to process (default: None for global)"
        )
        parser.add_argument(
            '--limit-regions', type=int, default=0, help='Limit number of initial regions considered (0 = no limit)'
        )
        parser.add_argument('--dry-run', action='store_true', help="Do not persist results")
        parser.add_argument('--verbose', action='store_true', help="Show detailed progress")
        parser.add_argument('--batch-size', type=int, default=500, help="Batch size for bulk operations (default 500)")

    def handle(self, *args, **options):
        periods = options['periods']
        region_ids = options.get('regions')
        category_ids = options.get('categories')
        limit_regions = options.get('limit_regions', 0)
        dry_run = options.get('dry_run', False)
        verbose = options.get('verbose', False)
        bulk_batch_size = options.get('batch_size', 500)

        period_map = {WEEKLY_CHOICE: 7, MONTHLY_CHOICE: 30, QUARTERLY_CHOICE: 90}

        # Validate periods
        for p in periods:
            if p not in period_map:
                raise CommandError(f"Invalid period: {p}")

        # Build initial region queryset (regions that have issues or explicit list)
        if region_ids:
            initial_qs = AdministrativeRegion.objects.filter(id__in=region_ids).order_by('id')
        else:
            initial_qs = AdministrativeRegion.objects.filter(issues__confirmed=True).distinct().order_by('id')

        if limit_regions > 0:
            initial_qs = initial_qs[:limit_regions]

        initial_regions = list(initial_qs)
        if not initial_regions:
            self.stdout.write(self.style.WARNING("No regions found to process."))
            return

        # Collect ancestors for each initial region (so we process ancestors too)
        region_map = {}
        to_process_ids = set()

        def collect_ancestors(region):
            ancestors = []
            cur = getattr(region, 'parent', None)
            while cur:
                ancestors.append(cur)
                cur = getattr(cur, 'parent', None)
            return ancestors

        for r in initial_regions:
            region_map[r.id] = r
            to_process_ids.add(r.id)
            for a in collect_ancestors(r):
                region_map[a.id] = a
                to_process_ids.add(a.id)

        regions_to_process = [region_map[rid] for rid in to_process_ids]

        # Order by depth (deeper first) so leaves are processed before ancestors (optional)
        def depth(region):
            d = 0
            cur = getattr(region, 'parent', None)
            while cur:
                d += 1
                cur = getattr(cur, 'parent', None)
            return d

        regions_to_process.sort(key=lambda r: depth(r), reverse=True)

        # Categories list
        if category_ids:
            categories = list(IssueCategory.objects.filter(id__in=category_ids).order_by('id'))
        else:
            # default: only global (None) and all categories
            categories = [None]

        self.stdout.write(
            self.style.SUCCESS(
                f"Processing {len(regions_to_process)} regions (including ancestors), {len(categories)} categories, {len(periods)} periods"
            )
        )

        # Prepare accumulators for bulk operations
        metrics_to_create = []
        metrics_to_update = []

        # Fields we will update in bulk_update (must be actual model fields)
        update_fields = [
            'open_issues_count',
            'avg_resolution_days',
            'active_workers_count',
            'total_workers_in_region',
            'open_issues_score',
            'resolution_score',
            'active_workers_score',
            'overall_performance_score',
            'calculated_at',
        ]

        total_tasks = 0
        errors = 0

        # Helper: compute metric data without persisting
        def compute_metric_data(region, category, period, days):
            """
            Try to obtain a dict of values for a RegionPerformanceMetrics row for the given
            (region, category, period).
            """
            # Preferred: model-level pure calculation helper
            return RegionPerformanceMetrics.calculate_data(region=region, category=category, period=period, days=days)

        # Iterate and accumulate
        for period in periods:
            days = period_map[period]
            for region in regions_to_process:
                for category in categories:
                    total_tasks += 1
                    try:
                        # Compute data (without persisting)
                        data = compute_metric_data(region=region, category=category, period=period, days=days)

                        # Determine whether an existing row exists (for this period + region + category)
                        existing = RegionPerformanceMetrics.objects.filter(
                            region=region, category=category, period=period
                        ).first()

                        if existing:
                            # Update fields on the existing instance (in-memory) and schedule for bulk_update
                            for key, value in data.items():
                                if hasattr(existing, key):
                                    setattr(existing, key, value)
                            # Ensure calculated_at is set
                            if not getattr(existing, 'calculated_at', None):
                                existing.calculated_at = data.get('calculated_at', timezone.now())
                            metrics_to_update.append(existing)
                        else:
                            # Create a new instance (not saved yet)
                            new_inst = RegionPerformanceMetrics(
                                region=region,
                                category=category,
                                period=period,
                                open_issues_count=data.get('open_issues_count', 0),
                                avg_resolution_days=data.get('avg_resolution_days', 0.0),
                                active_workers_count=data.get('active_workers_count', 0),
                                total_workers_in_region=data.get('total_workers_in_region', 0),
                                open_issues_score=data.get('open_issues_score', 0.0),
                                resolution_score=data.get('resolution_score', 0.0),
                                active_workers_score=data.get('active_workers_score', 0.0),
                                overall_performance_score=data.get('overall_performance_score', 0.0),
                                calculated_at=data.get('calculated_at', timezone.now()),
                            )
                            metrics_to_create.append(new_inst)

                        if verbose and total_tasks % 50 == 0:
                            self.stdout.write(
                                self.style.NOTICE(
                                    f"Prepared {total_tasks} tasks (create={len(metrics_to_create)}, update={len(metrics_to_update)})"
                                )
                            )

                    except Exception as exc:
                        errors += 1
                        self.stderr.write(
                            self.style.ERROR(
                                f"Error preparing metric for region={getattr(region,'id',None)} category={getattr(category,'id',None)} period={period}: {exc}"
                            )
                        )

        # If dry-run, do not persist; just report counts
        if dry_run:
            if verbose:
                self.stdout.write(
                    self.style.WARNING(
                        f"Dry-run: would create {len(metrics_to_create)} metrics and update {len(metrics_to_update)} metrics."
                    )
                )
            return

        # Persist in bulk inside a transaction
        persisted_created = 0
        persisted_updated = 0
        try:
            with transaction.atomic():
                if metrics_to_create:
                    RegionPerformanceMetrics.objects.bulk_create(metrics_to_create, batch_size=bulk_batch_size)
                    persisted_created = len(metrics_to_create)

                if metrics_to_update:
                    # bulk_update requires a list of model instances and the fields to update
                    RegionPerformanceMetrics.objects.bulk_update(
                        metrics_to_update, fields=update_fields, batch_size=bulk_batch_size
                    )
                    persisted_updated = len(metrics_to_update)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Persisted metrics: created={persisted_created}, updated={persisted_updated}, errors={errors}"
                )
            )
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Error persisting metrics in bulk: {exc}"))
            raise
