import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from authentication.models import User
from issues.models import AdministrativeRegion, Issue, IssueCategory, IssueStatus


class Command(BaseCommand):
    help = "Generate a minimal but varied set of confirmed Issues and Users so populate_performance_metrics yields non-trivial metrics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-regions",
            type=int,
            default=30,
            help="Maximum number of regions to create test issues for (default 30).",
        )
        parser.add_argument(
            "--max-categories",
            type=int,
            default=10,
            help="Maximum number of categories to use (default 10).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreate test issues with prefixed tracking_code (delete previous ones).",
        )

    def handle(self, *args, **options):
        max_regions = options["max_regions"]
        max_categories = options["max_categories"]
        force = options["force"]

        now = timezone.now()

        # Prefer regions that have at least one confirmed issue; ensure distinct
        regions_qs = AdministrativeRegion.objects.filter(issues__confirmed=True).distinct().order_by("id")
        if not regions_qs.exists():
            regions_qs = AdministrativeRegion.objects.all().order_by("id")
        regions = list(regions_qs[:max_regions])

        # Prefer categories that have at least one confirmed issue; ensure distinct
        categories_qs = IssueCategory.objects.filter(issues__confirmed=True).distinct().order_by("id")
        if not categories_qs.exists():
            categories_qs = IssueCategory.objects.all().order_by("id")
        categories = list(categories_qs[:max_categories])

        if not regions:
            self.stderr.write(self.style.ERROR("No AdministrativeRegion available in DB; aborting."))
            return
        if not categories:
            self.stderr.write(self.style.ERROR("No IssueCategory available in DB; aborting."))
            return

        # Ensure final status exists for resolved issues
        final_status = IssueStatus.objects.filter(final_status=True).first()
        if not final_status:
            final_status = IssueStatus.objects.create(name="Resolved (test)", final_status=True)

        # Period definitions (same durations used by PerformanceMetrics.calculate_and_save)
        periods = {
            "7d": {"days": 7},
            "30d": {"days": 30},
            "90d": {"days": 90},
        }

        tracking_prefix = "perf_test_tc_"
        if force:
            deleted = Issue.objects.filter(tracking_code__startswith=tracking_prefix).count()
            if deleted:
                Issue.objects.filter(tracking_code__startswith=tracking_prefix).delete()
                self.stdout.write(self.style.WARNING(f"Removed {deleted} previous test issues."))

        # Helper to reuse or create a user and set last_login
        def get_or_make_user(suffix, last_login_dt):
            # Prefer a real existing user that doesn't look like a test user
            existing = User.objects.filter(~Q(username__startswith="perf_test_user_")).first()
            if existing:
                existing.last_login = last_login_dt
                existing.save(update_fields=["last_login"])
                return existing
            any_user = User.objects.first()
            if any_user:
                any_user.last_login = last_login_dt
                any_user.save(update_fields=["last_login"])
                return any_user
            # Create a new test user
            username = f"perf_test_user_{suffix}"
            email = f"{username}@example.local"
            defaults = {"is_active": True, "email": email}
            user, created = User.objects.get_or_create(username=username, defaults=defaults)
            if created:
                user.set_unusable_password()
            user.last_login = last_login_dt
            if not user.email:
                user.email = email
            user.save(update_fields=["last_login", "email", "is_active"])
            return user

        created_issues = []
        created_users = set()

        with transaction.atomic():
            # Ensure at least one confirmed issue exists overall
            if not Issue.objects.filter(confirmed=True).exists():
                reporter = get_or_make_user("global", now - timedelta(days=1))
                issue = Issue.objects.create(
                    administrative_region=regions[0],
                    category=categories[0],
                    reporter=reporter,
                    intake_date=now - timedelta(days=1),
                    confirmed=True,
                    tracking_code=f"{tracking_prefix}global",
                    status=final_status,
                    resolution_date=now - timedelta(hours=12),
                    rating=5,  # ensure some rating data
                )
                created_issues.append(issue)
                created_users.add(reporter.id)

            # For each period create current and previous windows
            for pname, props in periods.items():
                days = props["days"]
                # Windows
                current_end = now
                prev_end = now - timedelta(days=days)

                # Create one user with last_login inside current window and one in previous window
                u_current = get_or_make_user(f"{pname}_curr", current_end - timedelta(days=max(1, days // 3)))
                u_prev = get_or_make_user(f"{pname}_prev", prev_end - timedelta(days=max(1, days // 3)))
                created_users.add(u_current.id)
                created_users.add(u_prev.id)

                # For a sample of regions (bounded) create issues in both windows with different resolution times and ratings
                sample_regions = regions[: min(len(regions), 20)]  # keep sample reasonable
                sample_categories = categories[: min(len(categories), 10)]

                for region in sample_regions:
                    # In current window: create 2 issues: one resolved fast, one unresolved or resolved slowly depending on desired delta
                    intake_curr_fast = current_end - timedelta(days=1)
                    tracking = f"{tracking_prefix}{pname}_r{region.id}_curr_fast"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        issue = Issue.objects.create(
                            administrative_region=region,
                            category=random.choice(sample_categories),
                            reporter=u_current,
                            intake_date=intake_curr_fast,
                            confirmed=True,
                            tracking_code=tracking,
                            status=final_status,
                            resolution_date=intake_curr_fast + timedelta(days=1),  # fast resolution
                            rating=random.choice([4, 5]),  # good rating in current
                            appeal_status=False,
                        )
                        created_issues.append(issue)

                    intake_curr_slow = current_end - timedelta(days=2)
                    tracking = f"{tracking_prefix}{pname}_r{region.id}_curr_slow"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        issue = Issue.objects.create(
                            administrative_region=region,
                            category=random.choice(sample_categories),
                            reporter=u_current,
                            intake_date=intake_curr_slow,
                            confirmed=True,
                            tracking_code=tracking,
                            status=final_status,
                            resolution_date=intake_curr_slow + timedelta(days=7),  # slow resolution
                            rating=random.choice([2, 3]),  # lower rating
                            appeal_status=random.choice([False, True]),
                        )
                        created_issues.append(issue)

                    # In previous window: create some issues with different resolution times to create non-trivial deltas
                    intake_prev_fast = prev_end - timedelta(days=1)
                    tracking = f"{tracking_prefix}{pname}_r{region.id}_prev_fast"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        issue = Issue.objects.create(
                            administrative_region=region,
                            category=random.choice(sample_categories),
                            reporter=u_prev,
                            intake_date=intake_prev_fast,
                            confirmed=True,
                            tracking_code=tracking,
                            status=final_status,
                            resolution_date=intake_prev_fast + timedelta(days=3),  # moderate resolution
                            rating=random.choice([3, 4]),
                            appeal_status=random.choice([False, True]),
                        )
                        created_issues.append(issue)

                    intake_prev_slow = prev_end - timedelta(days=3)
                    tracking = f"{tracking_prefix}{pname}_r{region.id}_prev_slow"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        issue = Issue.objects.create(
                            administrative_region=region,
                            category=random.choice(sample_categories),
                            reporter=u_prev,
                            intake_date=intake_prev_slow,
                            confirmed=True,
                            tracking_code=tracking,
                            status=final_status,
                            resolution_date=intake_prev_slow + timedelta(days=10),  # very slow
                            rating=random.choice([1, 2]),
                            appeal_status=random.choice([True]),  # ensure some appeals in prev window
                        )
                        created_issues.append(issue)

                # Create per-category issues in current and previous windows (ensure rated and appealed examples)
                for category in sample_categories:
                    intake_curr = current_end - timedelta(days=2)
                    tracking = f"{tracking_prefix}{pname}_c{category.id}_curr"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        issue = Issue.objects.create(
                            administrative_region=random.choice(sample_regions),
                            category=category,
                            reporter=u_current,
                            intake_date=intake_curr,
                            confirmed=True,
                            tracking_code=tracking,
                            status=final_status,
                            resolution_date=intake_curr + timedelta(days=random.choice([1, 2, 5])),
                            rating=random.choice([5, 4, 3]),
                            appeal_status=random.choice([False, True]),
                        )
                        created_issues.append(issue)

                    intake_prev = prev_end - timedelta(days=2)
                    tracking = f"{tracking_prefix}{pname}_c{category.id}_prev"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        issue = Issue.objects.create(
                            administrative_region=random.choice(sample_regions),
                            category=category,
                            reporter=u_prev,
                            intake_date=intake_prev,
                            confirmed=True,
                            tracking_code=tracking,
                            status=final_status,
                            resolution_date=intake_prev + timedelta(days=random.choice([4, 6, 10])),
                            rating=random.choice([1, 2, 3]),
                            appeal_status=random.choice([False, True]),
                        )
                        created_issues.append(issue)

                # A few region x category combos too
                combos_limit = 10
                combos_created = 0
                for region in sample_regions:
                    for category in sample_categories:
                        if combos_created >= combos_limit:
                            break
                        intake_curr = current_end - timedelta(days=1)
                        tracking = f"{tracking_prefix}{pname}_combo_r{region.id}_c{category.id}_curr"
                        if not Issue.objects.filter(tracking_code=tracking).exists():
                            issue = Issue.objects.create(
                                administrative_region=region,
                                category=category,
                                reporter=u_current,
                                intake_date=intake_curr,
                                confirmed=True,
                                tracking_code=tracking,
                                status=final_status,
                                resolution_date=intake_curr + timedelta(days=random.choice([1, 2, 7])),
                                rating=random.choice([5, 4, 3]),
                                appeal_status=random.choice([False, True]),
                            )
                            created_issues.append(issue)
                        intake_prev = prev_end - timedelta(days=1)
                        tracking = f"{tracking_prefix}{pname}_combo_r{region.id}_c{category.id}_prev"
                        if not Issue.objects.filter(tracking_code=tracking).exists():
                            issue = Issue.objects.create(
                                administrative_region=region,
                                category=category,
                                reporter=u_prev,
                                intake_date=intake_prev,
                                confirmed=True,
                                tracking_code=tracking,
                                status=final_status,
                                resolution_date=intake_prev + timedelta(days=random.choice([3, 8, 12])),
                                rating=random.choice([1, 2, 3]),
                                appeal_status=random.choice([False, True]),
                            )
                            created_issues.append(issue)
                        combos_created += 1
                    if combos_created >= combos_limit:
                        break

        self.stdout.write(self.style.SUCCESS(f"Created {len(created_issues)} test issues."))
        self.stdout.write(
            self.style.SUCCESS(f"Ensured {len(created_users)} users used/created with tailored last_login.")
        )

        self.stdout.write(
            self.style.NOTICE(
                "Now run: python manage.py populate_performance_metrics --create-global --create-regions "
                "--create-categories --create-region-category"
            )
        )
