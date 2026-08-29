import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from etl.management.commands.base_translated_command import TranslatedBaseCommand
from authentication.models import User
from issues.models import (
    AdministrativeRegion,
    Issue,
    IssueCategory,
    IssueStatus,
    IssueStatusChange,
)


class Command(TranslatedBaseCommand):
    help = "Create sample confirmed Issues for /dashboard/performance-diagnostics/ (plus IssueStatusChange history)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=20, help="Number of sample issues to create (default: 20)")
        parser.add_argument(
            "--prefix",
            type=str,
            default="pd_sample_",
            help="tracking_code prefix for created issues (default: pd_sample_)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete previous sample issues with the same prefix before creating new ones.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible generation (default: 42).",
        )
        parser.add_argument(
            "--regions-limit",
            type=int,
            default=200,
            help="Max number of AdministrativeRegion rows to sample from (default: 200).",
        )
        parser.add_argument(
            "--categories-limit",
            type=int,
            default=200,
            help="Max number of IssueCategory rows to sample from (default: 200).",
        )
        parser.add_argument(
            "--window-days",
            type=int,
            default=7,
            help="Create dates within the last N days so weekly metrics pick them up (default: 7).",
        )

    @transaction.atomic
    def handle_translated(self, *args, **options):
        count = int(options["count"] or 0)
        prefix = str(options["prefix"] or "pd_sample_")
        force = bool(options["force"])
        seed = int(options["seed"])
        regions_limit = int(options["regions_limit"])
        categories_limit = int(options["categories_limit"])
        window_days = int(options["window_days"])

        if count <= 0:
            self.stdout.write(self.style.WARNING("Nothing to do: --count must be > 0."))
            return

        random.seed(seed)
        now = timezone.now()

        regions = list(AdministrativeRegion.objects.all().order_by("id")[:regions_limit])
        categories = list(IssueCategory.objects.all().order_by("id")[:categories_limit])

        if not regions:
            self.stderr.write(self.style.ERROR("No AdministrativeRegion rows found. Load/create regions first."))
            return
        if not categories:
            self.stderr.write(self.style.ERROR("No IssueCategory rows found. Load/create categories first."))
            return

        non_terminal_statuses = list(
            IssueStatus.objects.filter(final_status=False, rejected_status=False).order_by("id")
        )
        if not non_terminal_statuses:
            self.stderr.write(
                self.style.ERROR("No non-terminal IssueStatus rows found (final_status=False, rejected_status=False).")
            )
            return

        open_status = (
            IssueStatus.objects.filter(open_status=True, final_status=False, rejected_status=False).order_by("id").first()
            or non_terminal_statuses[0]
        )
        final_status = IssueStatus.objects.filter(final_status=True).order_by("id").first() or IssueStatus.objects.order_by("id").first()
        if not final_status:
            self.stderr.write(self.style.ERROR("No IssueStatus rows found at all."))
            return

        reporter, _ = User.objects.get_or_create(
            username="pd_sample_reporter",
            defaults={"email": "pd_sample_reporter@example.local", "is_active": True},
        )
        if not reporter.email:
            reporter.email = "pd_sample_reporter@example.local"
            reporter.save(update_fields=["email"])

        if force:
            IssueStatusChange.objects.filter(issue__tracking_code__startswith=prefix).delete()
            deleted_issues, _ = Issue.objects.filter(tracking_code__startswith=prefix).delete()
            self.stdout.write(self.style.WARNING(f"Deleted previous sample data for prefix '{prefix}' (issues deleted: {deleted_issues})."))

        # Avoid collisions if you run multiple times without --force
        existing = Issue.objects.filter(tracking_code__startswith=prefix).count()
        start_idx = existing + 1

        created_issues = []
        created_isc = 0

        # Create a mix: first ~60% open, last ~40% resolved (within window)
        resolved_cutoff = int(round(count * 0.60))

        for n in range(count):
            i = start_idx + n

            region = random.choice(regions)
            category = random.choice(categories)

            # Keep dates within the target window so weekly snapshots pick them up.
            intake_date = now - timedelta(
                days=random.randint(0, max(0, window_days - 1)),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            is_resolved = n >= resolved_cutoff
            tracking_code = f"{prefix}{i:04d}"

            # Create with status=None to avoid Issue.save() auto-creating IssueStatusChange with entered_at=now.
            issue = Issue.objects.create(
                tracking_code=tracking_code,
                administrative_region=region,
                category=category,
                reporter=reporter,
                intake_date=intake_date,
                confirmed=True,
                status=None,
                rating=0,
                appeal_status=False,
                description=f"Sample issue {tracking_code} for Performance Diagnostics",
            )

            # Create a short non-terminal segment (closed) starting at intake_date.
            first_status = random.choice([s for s in non_terminal_statuses if s.id != open_status.id] or [open_status])
            first_entered = intake_date
            first_exited = first_entered + timedelta(days=random.randint(1, 3), hours=random.randint(0, 12))
            if first_exited >= now:
                first_exited = now - timedelta(minutes=30)
            if first_exited <= first_entered:
                first_exited = first_entered + timedelta(minutes=1)

            IssueStatusChange.objects.create(
                issue=issue,
                status=first_status,
                entered_at=first_entered,
                exited_at=first_exited,
            )
            created_isc += 1

            if is_resolved:
                # resolution_date must be after first_exited and within window
                resolution_date = max(
                    first_exited + timedelta(hours=2),
                    now - timedelta(days=random.randint(0, max(0, window_days - 1)), hours=random.randint(0, 23)),
                )
                if resolution_date > now:
                    resolution_date = now - timedelta(minutes=5)

                # Second closed segment in open_status until resolution
                IssueStatusChange.objects.create(
                    issue=issue,
                    status=open_status,
                    entered_at=first_exited,
                    exited_at=resolution_date,
                )
                created_isc += 1

                # Update terminal status + resolution_date without triggering Issue.save() side effects.
                Issue.objects.filter(pk=issue.pk).update(
                    status=final_status,
                    resolution_date=resolution_date,
                    rating=random.choice([3, 4, 5]),
                    appeal_status=random.choice([False, False, True]),
                )
            else:
                # Open issue: create an open IssueStatusChange row (exited_at=NULL)
                IssueStatusChange.objects.create(
                    issue=issue,
                    status=open_status,
                    entered_at=first_exited,
                    exited_at=None,
                )
                created_isc += 1

                Issue.objects.filter(pk=issue.pk).update(
                    status=open_status,
                    rating=random.choice([0, 0, 3, 4]),
                    appeal_status=random.choice([False, True]),
                )

            created_issues.append(issue)

        self.stdout.write(self.style.SUCCESS(f"✅ Created {len(created_issues)} Issues (prefix='{prefix}')"))
        self.stdout.write(self.style.SUCCESS(f"✅ Created {created_isc} IssueStatusChange rows"))
        self.stdout.write(self.style.NOTICE("Next, refresh Performance Diagnostics snapshot tables:"))
        self.stdout.write(
            self.style.NOTICE(
                "  python manage.py populate_performance_metrics --create-global --create-regions "
                "--create-categories --create-region-category --create-status-bottlenecks "
                "--limit-regions 20 --limit-categories 20"
            )
        )
        self.stdout.write(self.style.NOTICE("  python manage.py populate_region_performance_metrics --verbose"))

