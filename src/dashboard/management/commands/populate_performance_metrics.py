from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from dashboard.constants import (
    MONTHLY_CHOICE,
    PERIOD_CHOICES,
    QUARTERLY_CHOICE,
    WEEKLY_CHOICE,
)
from dashboard.models import PerformanceMetrics
from issues.models import AdministrativeRegion, IssueCategory


class Command(BaseCommand):
    help = "Populate PerformanceMetrics table for configured periods, regions and categories. Safe to run repeatedly."

    def add_arguments(self, parser):
        parser.add_argument(
            '--periods',
            nargs='+',
            type=str,
            default=[WEEKLY_CHOICE, MONTHLY_CHOICE, QUARTERLY_CHOICE],
            help="Periods to calculate (default: 7d 30d 90d)",
        )
        parser.add_argument(
            '--create-global',
            action='store_true',
            dest='create_global',
            help='Also create global metrics (no region, no category).',
        )
        parser.add_argument(
            '--create-regions',
            action='store_true',
            dest='create_regions',
            help='Create metrics per administrative region (all regions related to issues).',
        )
        parser.add_argument(
            '--create-categories',
            action='store_true',
            dest='create_categories',
            help='Create metrics per category (all categories).',
        )
        parser.add_argument(
            '--create-region-category',
            action='store_true',
            dest='create_region_category',
            help='Create metrics for each region x category combination.',
        )
        parser.add_argument(
            '--limit-regions',
            type=int,
            default=0,
            help='If >0 limit number of regions processed (useful for testing or migration).',
        )
        parser.add_argument(
            '--limit-categories',
            type=int,
            default=0,
            help='If >0 limit number of categories processed (useful for testing or migration).',
        )
        parser.add_argument(
            '--offset-regions',
            type=int,
            default=0,
            help='Offset for regions (use with --limit-regions to shard work).',
        )
        parser.add_argument(
            '--offset-categories',
            type=int,
            default=0,
            help='Offset for categories (use with --limit-categories to shard work).',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of operations between DB commits / progress messages (default 50).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Do everything but do not write changes (useful for testing).',
        )
        parser.add_argument(
            '--no-progress',
            action='store_true',
            help='Suppress progress output (useful for CI/Celery logs).',
        )

    def handle(self, *args, **options):
        periods = options['periods']
        create_global = options['create_global']
        create_regions = options['create_regions']
        create_categories = options['create_categories']
        create_region_category = options['create_region_category']
        limit_regions = options['limit_regions']
        limit_categories = options['limit_categories']
        offset_regions = options['offset_regions']
        offset_categories = options['offset_categories']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        no_progress = options['no_progress']

        # Validate period choices against model choices
        valid_periods = {choice[0] for choice in PERIOD_CHOICES}
        for p in periods:
            if p not in valid_periods:
                self.stderr.write(self.style.ERROR(f"Invalid period: {p}. Valid: {sorted(valid_periods)}"))
                return

        # loads the entire tree into memory (id->parent_id)
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
        categories_qs = IssueCategory.objects.all().order_by('id')

        if offset_regions:
            regions_qs = regions_qs[offset_regions:]
        if offset_categories:
            categories_qs = categories_qs[offset_categories:]

        if limit_regions > 0:
            regions = list(regions_qs[:limit_regions])
        else:
            regions = list(regions_qs)

        if limit_categories > 0:
            categories = list(categories_qs[:limit_categories])
        else:
            categories = list(categories_qs)

        tasks = []

        if create_global:
            for period in periods:
                tasks.append((period, None, None))

        if create_regions:
            for period in periods:
                for region in regions:
                    tasks.append((period, region, None))

        if create_categories:
            for period in periods:
                for category in categories:
                    tasks.append((period, None, category))

        if create_region_category:
            for period in periods:
                for region in regions:
                    for category in categories:
                        tasks.append((period, region, category))

        total_tasks = len(tasks)
        if total_tasks == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No tasks scheduled. Use --create-global, --create-regions, --create-categories or --create-region-category."
                )
            )
            return

        start = timezone.now()
        if not no_progress:
            self.stdout.write(self.style.NOTICE(f"Starting populate_performance_metrics at {start.isoformat()}"))
            self.stdout.write(self.style.NOTICE(f"Tasks scheduled: {total_tasks}"))

        processed = 0
        errors = 0

        # Process tasks in batches, commit every batch_size tasks
        for i, (period, region, category) in enumerate(tasks, start=1):
            processed += 1
            desc_parts = [f"period={period}"]
            if region:
                desc_parts.append(f"region_id={region.id}")
            else:
                desc_parts.append("region=ALL")
            if category:
                desc_parts.append(f"category_id={category.id}")
            else:
                desc_parts.append("category=ALL")
            desc = ", ".join(desc_parts)

            try:
                # Each metric save is atomic inside calculate_and_save (but we also guard overall)
                if dry_run:
                    # The safe approach is to call calculate_and_save but rollback, so use transaction.atomic and raise to rollback
                    with transaction.atomic():
                        PerformanceMetrics.calculate_and_save(period=period, region=region, category=category)
                        raise RuntimeError("dry-run rollback")
                else:
                    with transaction.atomic():
                        obj = PerformanceMetrics.calculate_and_save(period=period, region=region, category=category)
                if not no_progress:
                    self.stdout.write(
                        self.style.SUCCESS(f"[{processed}/{total_tasks}] Created/updated metrics id={obj.id} ({desc})")
                    )
            except RuntimeError:
                # dry-run intentional rollback
                if not no_progress:
                    self.stdout.write(self.style.NOTICE(f"[{processed}/{total_tasks}] dry-run calculated ({desc})"))
            except Exception as exc:
                errors += 1
                self.stderr.write(self.style.ERROR(f"[{processed}/{total_tasks}] ERROR processing ({desc}): {exc}"))

            # small flush/progress hint - space out large runs
            if i % batch_size == 0 and not no_progress:
                self.stdout.write(self.style.NOTICE(f"Progress: {i}/{total_tasks} tasks processed"))

        duration = timezone.now() - start
        if not no_progress:
            self.stdout.write(
                self.style.NOTICE(
                    f"Finished populate_performance_metrics: processed={processed}, errors={errors}, elapsed={duration}"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("populate_performance_metrics completed"))


# Command to create/update all metrics
# python manage.py populate_performance_metrics --create-global --create-regions --create-categories --create-region-category
