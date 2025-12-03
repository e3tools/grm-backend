import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from authentication.models import Facilitator, GovernmentWorker, User
from issues.models import (
    AdministrativeRegion,
    Issue,
    IssueCategory,
    IssueDepartment,
    IssueStatus,
)


class Command(BaseCommand):
    help = "Generate test data specifically for RegionPerformanceMetrics validation."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help="Delete previous test data and recreate",
        )
        parser.add_argument(
            '--regions',
            type=int,
            default=15,
            help="Number of regions to populate (default: 15)",
        )

    def handle(self, *args, **options):
        force = options['force']
        max_regions = options['regions']

        prefix = "rp_test_"
        now = timezone.now()

        if force:
            # Delete test issues and workers
            Issue.objects.filter(tracking_code__startswith=prefix).delete()
            GovernmentWorker.objects.filter(user__username__startswith=prefix).delete()
            Facilitator.objects.filter(user__username__startswith=prefix).delete()
            User.objects.filter(username__startswith=prefix).delete()
            self.stdout.write(self.style.WARNING("Removed previous test data."))

        # Get or verify required objects exist
        departments = list(IssueDepartment.objects.all()[:5])
        if not departments:
            self.stderr.write(
                self.style.ERROR("No IssueDepartment found. Please create at least one department first.")
            )
            return

        # Get regions with confirmed issues
        regions = list(
            AdministrativeRegion.objects.filter(issues__confirmed=True).distinct().order_by('id')[:max_regions]
        )

        if not regions:
            regions = list(AdministrativeRegion.objects.all().order_by('id')[:max_regions])

        if not regions:
            self.stderr.write(self.style.ERROR("No regions available."))
            return

        # Get categories
        categories = list(IssueCategory.objects.all().order_by('id')[:5])
        if not categories:
            self.stderr.write(self.style.ERROR("No categories available."))
            return

        # Get statuses
        open_status = IssueStatus.objects.filter(open_status=True).first()
        final_status = IssueStatus.objects.filter(final_status=True).first()

        if not open_status or not final_status:
            self.stderr.write(self.style.ERROR("Missing required IssueStatus objects."))
            return

        # Find the region with the largest number of direct children
        # and ensure each leaf descendant of that region has at least one confirmed Issue.
        try:
            # Compute child counts in Python to avoid relying on a specific related_name
            all_regions = AdministrativeRegion.objects.all()
            max_children_region = None
            max_children_count = -1
            for r in all_regions:
                child_count = AdministrativeRegion.objects.filter(parent=r).count()
                if child_count > max_children_count:
                    max_children_count = child_count
                    max_children_region = r

            if max_children_region:
                # Get all descendant ids using model helper if available, otherwise include the region itself
                if hasattr(max_children_region, "get_descendant_ids"):
                    descendant_ids = max_children_region.get_descendant_ids()
                else:
                    # fallback: include direct children and the region itself
                    descendant_ids = [max_children_region.id] + list(
                        AdministrativeRegion.objects.filter(parent=max_children_region).values_list('id', flat=True)
                    )

                # Identify leaf regions among descendants: those with no children
                leaf_regions = []
                for rid in descendant_ids:
                    try:
                        region_obj = AdministrativeRegion.objects.get(id=rid)
                    except AdministrativeRegion.DoesNotExist:
                        continue
                    has_children = AdministrativeRegion.objects.filter(parent=region_obj).exists()
                    if not has_children:
                        leaf_regions.append(region_obj)

                # Ensure each leaf has at least one confirmed Issue; create one if missing
                for leaf in leaf_regions:
                    exists = Issue.objects.filter(administrative_region=leaf, confirmed=True).exists()
                    if not exists:
                        reporter = User.objects.filter(is_active=True).first()
                        if not reporter:
                            reporter = User.objects.create(
                                username=f"{prefix}reporter_{leaf.id}",
                                email=f"{prefix}reporter_{leaf.id}@test.local",
                                is_active=True,
                            )
                        Issue.objects.create(
                            tracking_code=f"{prefix}leaf_{leaf.id}_1",
                            administrative_region=leaf,
                            category=random.choice(categories),
                            reporter=reporter,
                            intake_date=now,
                            confirmed=True,
                            status=open_status,
                            rating=0,
                            appeal_status=False,
                        )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Ensured {len(leaf_regions)} leaf regions under '{max_children_region.name}' have at least one confirmed issue."
                    )
                )
        except Exception as e:
            # Non-fatal: report and continue with normal generation
            self.stderr.write(self.style.WARNING(f"Could not ensure leaf coverage: {e}"))

        created_workers = 0
        created_issues = 0

        with transaction.atomic():
            # Create test data for each region
            for idx, region in enumerate(regions):
                # Scenario 1: CRITICAL region (high open issues, slow resolution, few workers)
                if idx % 3 == 0:
                    scenario = "critical"
                    num_workers = random.randint(2, 4)
                    num_open_issues = random.randint(55, 80)
                    num_resolved_issues = random.randint(5, 10)
                    resolution_days_range = (18, 30)

                # Scenario 2: AT RISK region (moderate metrics)
                elif idx % 3 == 1:
                    scenario = "at_risk"
                    num_workers = random.randint(5, 8)
                    num_open_issues = random.randint(25, 45)
                    num_resolved_issues = random.randint(15, 25)
                    resolution_days_range = (8, 14)

                # Scenario 3: GOOD region (low open issues, fast resolution, many workers)
                else:
                    scenario = "good"
                    num_workers = random.randint(12, 20)
                    num_open_issues = random.randint(5, 18)
                    num_resolved_issues = random.randint(30, 50)
                    resolution_days_range = (2, 6)

                # Create workers for this region
                for w_idx in range(num_workers):
                    # Randomly choose worker type
                    is_gov_worker = random.choice([True, False])

                    username = f"{prefix}worker_{region.id}_{w_idx}"
                    user = User.objects.create(
                        username=username,
                        email=f"{username}@test.local",
                        is_active=True,
                    )
                    user.set_unusable_password()

                    # Set last_login to random time in last 7 days (for active workers metric)
                    if scenario == "good" or (scenario == "at_risk" and w_idx < num_workers // 2):
                        # Active workers
                        user.last_login = now - timedelta(days=random.randint(1, 6))
                    else:
                        # Inactive workers (logged in >7 days ago)
                        user.last_login = now - timedelta(days=random.randint(15, 60))

                    user.save()

                    if is_gov_worker:
                        # FIXED: GovernmentWorker requires department
                        department = random.choice(departments)
                        GovernmentWorker.objects.create(
                            user=user,
                            administrative_region=region,
                            department=department,
                        )
                    else:
                        Facilitator.objects.create(
                            user=user,
                            administrative_region=region,
                        )

                    created_workers += 1

                # Create OPEN issues
                for i in range(num_open_issues):
                    tracking_code = f"{prefix}open_{region.id}_{i}"
                    intake_date = now - timedelta(days=random.randint(1, 30))

                    # Use first user as reporter (or create a reporter if needed)
                    reporter = User.objects.filter(is_active=True).first()
                    if not reporter:
                        reporter = User.objects.create(
                            username=f"{prefix}reporter",
                            email=f"{prefix}reporter@test.local",
                            is_active=True,
                        )

                    Issue.objects.create(
                        tracking_code=tracking_code,
                        administrative_region=region,
                        category=random.choice(categories),
                        reporter=reporter,
                        intake_date=intake_date,
                        confirmed=True,
                        status=open_status,
                        rating=0,
                        appeal_status=False,
                    )
                    created_issues += 1

                # Create RESOLVED issues
                for i in range(num_resolved_issues):
                    tracking_code = f"{prefix}resolved_{region.id}_{i}"
                    resolution_days = random.randint(*resolution_days_range)
                    intake_date = now - timedelta(days=30 + resolution_days)
                    resolution_date = intake_date + timedelta(days=resolution_days)

                    reporter = User.objects.filter(is_active=True).first()

                    Issue.objects.create(
                        tracking_code=tracking_code,
                        administrative_region=region,
                        category=random.choice(categories),
                        reporter=reporter,
                        intake_date=intake_date,
                        resolution_date=resolution_date,
                        confirmed=True,
                        status=final_status,
                        rating=random.choice([3, 4, 5]),
                        appeal_status=random.choice([False, False, True]),
                    )
                    created_issues += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Region {region.name} ({scenario}): "
                        f"{num_workers} workers, {num_open_issues} open, "
                        f"{num_resolved_issues} resolved"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Created {created_workers} workers and {created_issues} issues " f"across {len(regions)} regions"
            )
        )
        self.stdout.write(
            self.style.NOTICE(
                "\nNext steps:\n"
                "1. python manage.py populate_region_performance_metrics --verbose\n"
                "2. Access /dashboard/performance-diagnostics/ to view results"
            )
        )
