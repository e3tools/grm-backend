"""
Generate a minimal but varied set of confirmed Issues, Users and a minimal set of
IssueStatusChange rows so that populate_performance_metrics and
StatusBottleneckMetricsAPIView show non-trivial and diverse results.

This script reuses existing IssueStatus objects from the database. It will not
create new IssueStatus rows. For non-terminal statuses it creates IssueStatusChange
rows when appropriate. For terminal statuses (final/rejected) it creates Issues
but does not create IssueStatusChange rows (per project convention).
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from authentication.models import User
from dashboard.constants import MONTHLY_CHOICE, QUARTERLY_CHOICE, WEEKLY_CHOICE
from issues.models import (
    AdministrativeRegion,
    Issue,
    IssueCategory,
    IssueStatus,
    IssueStatusChange,
)


class Command(BaseCommand):
    help = "Generate a minimal but varied set of confirmed Issues, Users and IssueStatusChange rows."

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
        tracking_prefix = "perf_test_tc_"

        # If force, remove previous test issues and their status changes
        if force:
            IssueStatusChange.objects.filter(issue__tracking_code__startswith=tracking_prefix).delete()
            Issue.objects.filter(tracking_code__startswith=tracking_prefix).delete()
            self.stdout.write(self.style.WARNING("Removed previous perf_test issues and status changes."))

        # Choose regions and categories (prefer ones that already have confirmed issues)
        regions_qs = AdministrativeRegion.objects.filter(issues__confirmed=True).distinct().order_by("id")
        if not regions_qs.exists():
            regions_qs = AdministrativeRegion.objects.all().order_by("id")
        regions = list(regions_qs[:max_regions])

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

        # Discover existing IssueStatus objects by role (do not create new statuses)
        initial_statuses = list(IssueStatus.objects.filter(initial_status=True))
        open_statuses = list(IssueStatus.objects.filter(open_status=True))
        final_statuses = list(IssueStatus.objects.filter(final_status=True))
        rejected_statuses = list(IssueStatus.objects.filter(rejected_status=True))
        # Generic non-terminal statuses: not final and not rejected
        generic_statuses = list(IssueStatus.objects.filter(final_status=False, rejected_status=False))

        # Log availability
        roles_availability = {
            "initial": bool(initial_statuses),
            "open": bool(open_statuses),
            "generic_non_terminal": bool(generic_statuses),
            "final": bool(final_statuses),
            "rejected": bool(rejected_statuses),
        }
        self.stdout.write(self.style.NOTICE(f"IssueStatus roles availability: {roles_availability}"))

        # Period definitions (same durations used by PerformanceMetrics.calculate_and_save)
        periods = {
            WEEKLY_CHOICE: {"days": 7},
            MONTHLY_CHOICE: {"days": 30},
            QUARTERLY_CHOICE: {"days": 90},
        }

        # Helper to reuse or create a user and set last_login
        def get_or_make_user(suffix, last_login_dt):
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

        # Helper to create IssueStatusChange safely (avoid duplicate open ISC per issue)
        def create_isc_safe(issue, status, entered_at, exited_at):
            """
            Create or update IssueStatusChange safely:
              - If exited_at is None (open ISC): create only if no open ISC exists for the issue.
              - If exited_at is not None (closed ISC): if an open ISC exists, set its exited_at to the provided exited_at;
                otherwise create a new ISC with exited_at set.
            Returns the created/updated IssueStatusChange instance or None if skipped.
            """
            # Check for existing open ISC for this issue
            open_qs = IssueStatusChange.objects.filter(issue=issue, exited_at__isnull=True).order_by('-entered_at')
            open_isc = open_qs.first()

            if exited_at is None:
                # We want to create an open ISC
                if open_isc:
                    # There's already an open ISC for this issue: skip creation
                    return None
                # No open ISC exists: create one
                return IssueStatusChange.objects.create(
                    issue=issue,
                    status=status,
                    entered_at=entered_at,
                    exited_at=None,
                )
            else:
                # We want to create a closed ISC (exited_at provided)
                if open_isc:
                    # Close the existing open ISC instead of creating a new open one
                    # Ensure exited_at is not earlier than entered_at; if it is, set to entered_at + 1 second
                    if exited_at <= open_isc.entered_at:
                        open_isc.exited_at = open_isc.entered_at + timedelta(seconds=1)
                    else:
                        open_isc.exited_at = exited_at
                    open_isc.save(update_fields=['exited_at'])
                    return open_isc
                else:
                    # No open ISC exists: create a closed ISC row
                    return IssueStatusChange.objects.create(
                        issue=issue,
                        status=status,
                        entered_at=entered_at,
                        exited_at=exited_at,
                    )

        created_issues = []
        created_users = set()
        created_status_changes = []

        with transaction.atomic():
            # Ensure at least one confirmed issue exists overall (keeps previous behavior)
            if not Issue.objects.filter(confirmed=True).exists():
                reporter = get_or_make_user("global", now - timedelta(days=1))
                # Prefer a final status if available, otherwise any status
                fallback_status = (
                    final_statuses[0]
                    if final_statuses
                    else (
                        generic_statuses[0]
                        if generic_statuses
                        else (
                            open_statuses[0] if open_statuses else (initial_statuses[0] if initial_statuses else None)
                        )
                    )
                )
                issue = Issue.objects.create(
                    administrative_region=regions[0],
                    category=categories[0],
                    reporter=reporter,
                    intake_date=now - timedelta(days=1),
                    confirmed=True,
                    tracking_code=f"{tracking_prefix}global",
                    status=fallback_status,
                    resolution_date=(
                        (now - timedelta(hours=12))
                        if (fallback_status and getattr(fallback_status, "final_status", False))
                        else None
                    ),
                    rating=5,
                )
                created_issues.append(issue)
                created_users.add(reporter.id)

            # For each period create current and previous windows and preserve diversity (ratings, appeals, etc.)
            for pname, props in periods.items():
                days = props["days"]
                current_end = now
                prev_end = now - timedelta(days=days)

                # Create users for current and previous windows
                u_current = get_or_make_user(f"{pname}_curr", current_end - timedelta(days=max(1, days // 3)))
                u_prev = get_or_make_user(f"{pname}_prev", prev_end - timedelta(days=max(1, days // 3)))
                created_users.add(u_current.id)
                created_users.add(u_prev.id)

                sample_regions = regions[: min(len(regions), 20)]
                sample_categories = categories[: min(len(categories), 10)]

                # Preserve original diversity: per-region and per-category issues with varied ratings and appeal flags
                for region in sample_regions:
                    # Current window: fast resolved
                    intake_curr_fast = current_end - timedelta(days=1)
                    tracking = f"{tracking_prefix}{pname}_r{region.id}_curr_fast"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        # choose a status for resolved issues: prefer final_status if available
                        status_for_resolved = (
                            final_statuses[0] if final_statuses else (generic_statuses[0] if generic_statuses else None)
                        )
                        issue = Issue.objects.create(
                            administrative_region=region,
                            category=random.choice(sample_categories),
                            reporter=u_current,
                            intake_date=intake_curr_fast,
                            confirmed=True,
                            tracking_code=tracking,
                            status=status_for_resolved,
                            resolution_date=(
                                intake_curr_fast + timedelta(days=1)
                                if status_for_resolved and getattr(status_for_resolved, "final_status", False)
                                else None
                            ),
                            rating=random.choice([4, 5]),
                            appeal_status=False,
                        )
                        created_issues.append(issue)

                        # Create a short previous ISC (closed) to simulate a transition into this status
                        if generic_statuses:
                            prev_status = random.choice(generic_statuses)
                            prev_entered = intake_curr_fast - timedelta(days=random.randint(3, 7))
                            prev_exited = intake_curr_fast - timedelta(days=random.randint(1, 2))
                            isc_prev = create_isc_safe(
                                issue=issue, status=prev_status, entered_at=prev_entered, exited_at=prev_exited
                            )
                            if isc_prev:
                                created_status_changes.append(isc_prev)

                        # Create IssueStatusChange for current status (closed if resolved)
                        if (
                            issue.status
                            and not getattr(issue.status, "final_status", False)
                            and not getattr(issue.status, "rejected_status", False)
                        ):
                            isc = create_isc_safe(
                                issue=issue,
                                status=issue.status,
                                entered_at=issue.intake_date,
                                exited_at=issue.resolution_date,
                            )
                            if isc:
                                created_status_changes.append(isc)
                        else:
                            # If terminal, still create a closed ISC representing time-in-status before resolution
                            if issue.resolution_date:
                                isc = create_isc_safe(
                                    issue=issue,
                                    status=issue.status,
                                    entered_at=issue.intake_date - timedelta(days=1),
                                    exited_at=issue.resolution_date,
                                )
                                if isc:
                                    created_status_changes.append(isc)

                    # Current window: slow resolved
                    intake_curr_slow = current_end - timedelta(days=2)
                    tracking = f"{tracking_prefix}{pname}_r{region.id}_curr_slow"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        status_for_resolved = (
                            final_statuses[0] if final_statuses else (generic_statuses[0] if generic_statuses else None)
                        )
                        issue = Issue.objects.create(
                            administrative_region=region,
                            category=random.choice(sample_categories),
                            reporter=u_current,
                            intake_date=intake_curr_slow,
                            confirmed=True,
                            tracking_code=tracking,
                            status=status_for_resolved,
                            resolution_date=(
                                intake_curr_slow + timedelta(days=7)
                                if status_for_resolved and getattr(status_for_resolved, "final_status", False)
                                else None
                            ),
                            rating=random.choice([2, 3]),
                            appeal_status=random.choice([False, True]),
                        )
                        created_issues.append(issue)

                        # Create a previous closed ISC and a current closed ISC with longer duration
                        if generic_statuses:
                            prev_status = random.choice(generic_statuses)
                            prev_entered = intake_curr_slow - timedelta(days=random.randint(5, 12))
                            prev_exited = intake_curr_slow - timedelta(days=random.randint(2, 4))
                            isc_prev = create_isc_safe(
                                issue=issue, status=prev_status, entered_at=prev_entered, exited_at=prev_exited
                            )
                            if isc_prev:
                                created_status_changes.append(isc_prev)

                        if (
                            issue.status
                            and not getattr(issue.status, "final_status", False)
                            and not getattr(issue.status, "rejected_status", False)
                        ):
                            isc = create_isc_safe(
                                issue=issue,
                                status=issue.status,
                                entered_at=issue.intake_date,
                                exited_at=issue.resolution_date,
                            )
                            if isc:
                                created_status_changes.append(isc)
                        else:
                            if issue.resolution_date:
                                isc = create_isc_safe(
                                    issue=issue,
                                    status=issue.status,
                                    entered_at=issue.intake_date - timedelta(days=2),
                                    exited_at=issue.resolution_date,
                                )
                                if isc:
                                    created_status_changes.append(isc)

                    # Previous window: moderate and slow examples
                    intake_prev_fast = prev_end - timedelta(days=1)
                    tracking = f"{tracking_prefix}{pname}_r{region.id}_prev_fast"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        status_for_resolved = (
                            final_statuses[0] if final_statuses else (generic_statuses[0] if generic_statuses else None)
                        )
                        issue = Issue.objects.create(
                            administrative_region=region,
                            category=random.choice(sample_categories),
                            reporter=u_prev,
                            intake_date=intake_prev_fast,
                            confirmed=True,
                            tracking_code=tracking,
                            status=status_for_resolved,
                            resolution_date=(
                                intake_prev_fast + timedelta(days=3)
                                if status_for_resolved and getattr(status_for_resolved, "final_status", False)
                                else None
                            ),
                            rating=random.choice([3, 4]),
                            appeal_status=random.choice([False, True]),
                        )
                        created_issues.append(issue)

                        # Create two closed ISC rows to simulate a transition chain
                        if generic_statuses:
                            first_status = random.choice(generic_statuses)
                            second_status = random.choice(
                                [s for s in generic_statuses if s != first_status] or generic_statuses
                            )
                            first_entered = intake_prev_fast - timedelta(days=random.randint(8, 15))
                            first_exited = intake_prev_fast - timedelta(days=random.randint(4, 6))
                            isc1 = create_isc_safe(
                                issue=issue, status=first_status, entered_at=first_entered, exited_at=first_exited
                            )
                            if isc1:
                                created_status_changes.append(isc1)
                            second_entered = first_exited + timedelta(days=1)
                            second_exited = intake_prev_fast - timedelta(days=random.randint(1, 2))
                            isc2 = create_isc_safe(
                                issue=issue, status=second_status, entered_at=second_entered, exited_at=second_exited
                            )
                            if isc2:
                                created_status_changes.append(isc2)

                        # Current/terminal ISC
                        if (
                            issue.status
                            and not getattr(issue.status, "final_status", False)
                            and not getattr(issue.status, "rejected_status", False)
                        ):
                            isc = create_isc_safe(
                                issue=issue,
                                status=issue.status,
                                entered_at=issue.intake_date,
                                exited_at=issue.resolution_date,
                            )
                            if isc:
                                created_status_changes.append(isc)
                        else:
                            if issue.resolution_date:
                                isc = create_isc_safe(
                                    issue=issue,
                                    status=issue.status,
                                    entered_at=issue.intake_date - timedelta(days=3),
                                    exited_at=issue.resolution_date,
                                )
                                if isc:
                                    created_status_changes.append(isc)

                    intake_prev_slow = prev_end - timedelta(days=3)
                    tracking = f"{tracking_prefix}{pname}_r{region.id}_prev_slow"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        status_for_resolved = (
                            final_statuses[0] if final_statuses else (generic_statuses[0] if generic_statuses else None)
                        )
                        issue = Issue.objects.create(
                            administrative_region=region,
                            category=random.choice(sample_categories),
                            reporter=u_prev,
                            intake_date=intake_prev_slow,
                            confirmed=True,
                            tracking_code=tracking,
                            status=status_for_resolved,
                            resolution_date=(
                                intake_prev_slow + timedelta(days=10)
                                if status_for_resolved and getattr(status_for_resolved, "final_status", False)
                                else None
                            ),
                            rating=random.choice([1, 2]),
                            appeal_status=random.choice([True]),
                        )
                        created_issues.append(issue)
                        # Create a closed ISC with long duration
                        if generic_statuses:
                            prev_status = random.choice(generic_statuses)
                            prev_entered = intake_prev_slow - timedelta(days=random.randint(12, 25))
                            prev_exited = intake_prev_slow - timedelta(days=random.randint(6, 9))
                            isc_prev = create_isc_safe(
                                issue=issue, status=prev_status, entered_at=prev_entered, exited_at=prev_exited
                            )
                            if isc_prev:
                                created_status_changes.append(isc_prev)
                        if (
                            issue.status
                            and not getattr(issue.status, "final_status", False)
                            and not getattr(issue.status, "rejected_status", False)
                        ):
                            isc = create_isc_safe(
                                issue=issue,
                                status=issue.status,
                                entered_at=issue.intake_date,
                                exited_at=issue.resolution_date,
                            )
                            if isc:
                                created_status_changes.append(isc)
                        else:
                            if issue.resolution_date:
                                isc = create_isc_safe(
                                    issue=issue,
                                    status=issue.status,
                                    entered_at=issue.intake_date - timedelta(days=4),
                                    exited_at=issue.resolution_date,
                                )
                                if isc:
                                    created_status_changes.append(isc)

                    # --- explicit open_status scenario to ensure open_status IssueStatusChange rows are created ---
                    if open_statuses:
                        open_status = open_statuses[0]
                        tracking = f"{tracking_prefix}{pname}_open_r{region.id}"
                        if not Issue.objects.filter(tracking_code=tracking).exists():
                            issue_open = Issue.objects.create(
                                administrative_region=region,
                                category=random.choice(sample_categories),
                                reporter=u_current,
                                intake_date=current_end - timedelta(days=2),
                                confirmed=True,
                                tracking_code=tracking,
                                status=open_status,
                                resolution_date=(
                                    (current_end - timedelta(days=1))
                                    if getattr(open_status, "final_status", False)
                                    else None
                                ),
                                rating=random.choice([3, 4]),
                                appeal_status=random.choice([False, True]),
                            )
                            created_issues.append(issue_open)
                            # create IssueStatusChange for open_status (only if non-terminal)
                            if not getattr(open_status, "final_status", False) and not getattr(
                                open_status, "rejected_status", False
                            ):
                                # create a closed ISC first to simulate history, then an open ISC
                                hist_entered = issue_open.intake_date - timedelta(days=random.randint(5, 12))
                                hist_exited = issue_open.intake_date - timedelta(days=random.randint(2, 4))
                                hist_isc = create_isc_safe(
                                    issue=issue_open,
                                    status=random.choice(generic_statuses) if generic_statuses else open_status,
                                    entered_at=hist_entered,
                                    exited_at=hist_exited,
                                )
                                if hist_isc:
                                    created_status_changes.append(hist_isc)
                                isc = create_isc_safe(
                                    issue=issue_open,
                                    status=open_status,
                                    entered_at=issue_open.intake_date,
                                    exited_at=issue_open.resolution_date,
                                )
                                if isc:
                                    created_status_changes.append(isc)
                    else:
                        # If no open_status exists, log a warning (keeps behavior explicit)
                        self.stdout.write(
                            self.style.WARNING(
                                f"No IssueStatus with open_status=True; skipping explicit open scenario for region {region.id}."
                            )
                        )

                # Per-category examples (preserve rating diversity)
                for category in sample_categories:
                    intake_curr = current_end - timedelta(days=2)
                    tracking = f"{tracking_prefix}{pname}_c{category.id}_curr"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        # choose a status that may be terminal or not depending on availability
                        status_choice = (
                            generic_statuses[0]
                            if generic_statuses
                            else (
                                open_statuses[0]
                                if open_statuses
                                else (
                                    initial_statuses[0]
                                    if initial_statuses
                                    else (final_statuses[0] if final_statuses else None)
                                )
                            )
                        )
                        issue = Issue.objects.create(
                            administrative_region=random.choice(sample_regions),
                            category=category,
                            reporter=u_current,
                            intake_date=intake_curr,
                            confirmed=True,
                            tracking_code=tracking,
                            status=status_choice,
                            resolution_date=(
                                (intake_curr + timedelta(days=random.choice([1, 2, 5])))
                                if status_choice and getattr(status_choice, "final_status", False)
                                else None
                            ),
                            rating=random.choice([5, 4, 3]),
                            appeal_status=random.choice([False, True]),
                        )
                        created_issues.append(issue)
                        # create a previous closed ISC and a current ISC
                        if generic_statuses:
                            prev_status = random.choice(generic_statuses)
                            prev_entered = intake_curr - timedelta(days=random.randint(4, 9))
                            prev_exited = intake_curr - timedelta(days=random.randint(1, 3))
                            isc_prev = create_isc_safe(
                                issue=issue, status=prev_status, entered_at=prev_entered, exited_at=prev_exited
                            )
                            if isc_prev:
                                created_status_changes.append(isc_prev)
                        if (
                            issue.status
                            and not getattr(issue.status, "final_status", False)
                            and not getattr(issue.status, "rejected_status", False)
                        ):
                            isc = create_isc_safe(
                                issue=issue,
                                status=issue.status,
                                entered_at=issue.intake_date,
                                exited_at=issue.resolution_date,
                            )
                            if isc:
                                created_status_changes.append(isc)

                    intake_prev = prev_end - timedelta(days=2)
                    tracking = f"{tracking_prefix}{pname}_c{category.id}_prev"
                    if not Issue.objects.filter(tracking_code=tracking).exists():
                        status_choice = (
                            generic_statuses[0]
                            if generic_statuses
                            else (
                                open_statuses[0]
                                if open_statuses
                                else (
                                    initial_statuses[0]
                                    if initial_statuses
                                    else (final_statuses[0] if final_statuses else None)
                                )
                            )
                        )
                        issue = Issue.objects.create(
                            administrative_region=random.choice(sample_regions),
                            category=category,
                            reporter=u_prev,
                            intake_date=intake_prev,
                            confirmed=True,
                            tracking_code=tracking,
                            status=status_choice,
                            resolution_date=(
                                (intake_prev + timedelta(days=random.choice([4, 6, 10])))
                                if status_choice and getattr(status_choice, "final_status", False)
                                else None
                            ),
                            rating=random.choice([1, 2, 3]),
                            appeal_status=random.choice([False, True]),
                        )
                        created_issues.append(issue)
                        if generic_statuses:
                            prev_status = random.choice(generic_statuses)
                            prev_entered = intake_prev - timedelta(days=random.randint(6, 14))
                            prev_exited = intake_prev - timedelta(days=random.randint(2, 4))
                            isc_prev = create_isc_safe(
                                issue=issue, status=prev_status, entered_at=prev_entered, exited_at=prev_exited
                            )
                            if isc_prev:
                                created_status_changes.append(isc_prev)
                        if (
                            issue.status
                            and not getattr(issue.status, "final_status", False)
                            and not getattr(issue.status, "rejected_status", False)
                        ):
                            isc = create_isc_safe(
                                issue=issue,
                                status=issue.status,
                                entered_at=issue.intake_date,
                                exited_at=issue.resolution_date,
                            )
                            if isc:
                                created_status_changes.append(isc)

                # Region x category combos (bounded) to preserve variety
                combos_limit = 10
                combos_created = 0
                for region in sample_regions:
                    for category in sample_categories:
                        if combos_created >= combos_limit:
                            break
                        intake_curr = current_end - timedelta(days=1)
                        tracking = f"{tracking_prefix}{pname}_combo_r{region.id}_c{category.id}_curr"
                        if not Issue.objects.filter(tracking_code=tracking).exists():
                            status_choice = (
                                generic_statuses[0]
                                if generic_statuses
                                else (
                                    open_statuses[0]
                                    if open_statuses
                                    else (
                                        initial_statuses[0]
                                        if initial_statuses
                                        else (final_statuses[0] if final_statuses else None)
                                    )
                                )
                            )
                            issue = Issue.objects.create(
                                administrative_region=region,
                                category=category,
                                reporter=u_current,
                                intake_date=intake_curr,
                                confirmed=True,
                                tracking_code=tracking,
                                status=status_choice,
                                resolution_date=(
                                    (intake_curr + timedelta(days=random.choice([1, 2, 7])))
                                    if status_choice and getattr(status_choice, "final_status", False)
                                    else None
                                ),
                                rating=random.choice([5, 4, 3]),
                                appeal_status=random.choice([False, True]),
                            )
                            created_issues.append(issue)
                            # create a previous closed ISC and a current ISC
                            if generic_statuses:
                                prev_status = random.choice(generic_statuses)
                                prev_entered = intake_curr - timedelta(days=random.randint(3, 10))
                                prev_exited = intake_curr - timedelta(days=random.randint(1, 2))
                                isc_prev = create_isc_safe(
                                    issue=issue, status=prev_status, entered_at=prev_entered, exited_at=prev_exited
                                )
                                if isc_prev:
                                    created_status_changes.append(isc_prev)
                            if (
                                issue.status
                                and not getattr(issue.status, "final_status", False)
                                and not getattr(issue.status, "rejected_status", False)
                            ):
                                isc = create_isc_safe(
                                    issue=issue,
                                    status=issue.status,
                                    entered_at=issue.intake_date,
                                    exited_at=issue.resolution_date,
                                )
                                if isc:
                                    created_status_changes.append(isc)

                        intake_prev = prev_end - timedelta(days=1)
                        tracking = f"{tracking_prefix}{pname}_combo_r{region.id}_c{category.id}_prev"
                        if not Issue.objects.filter(tracking_code=tracking).exists():
                            status_choice = (
                                generic_statuses[0]
                                if generic_statuses
                                else (
                                    open_statuses[0]
                                    if open_statuses
                                    else (
                                        initial_statuses[0]
                                        if initial_statuses
                                        else (final_statuses[0] if final_statuses else None)
                                    )
                                )
                            )
                            issue = Issue.objects.create(
                                administrative_region=region,
                                category=category,
                                reporter=u_prev,
                                intake_date=intake_prev,
                                confirmed=True,
                                tracking_code=tracking,
                                status=status_choice,
                                resolution_date=(
                                    (intake_prev + timedelta(days=random.choice([3, 8, 12])))
                                    if status_choice and getattr(status_choice, "final_status", False)
                                    else None
                                ),
                                rating=random.choice([1, 2, 3]),
                                appeal_status=random.choice([False, True]),
                            )
                            created_issues.append(issue)
                            if generic_statuses:
                                prev_status = random.choice(generic_statuses)
                                prev_entered = intake_prev - timedelta(days=random.randint(5, 12))
                                prev_exited = intake_prev - timedelta(days=random.randint(2, 4))
                                isc_prev = create_isc_safe(
                                    issue=issue, status=prev_status, entered_at=prev_entered, exited_at=prev_exited
                                )
                                if isc_prev:
                                    created_status_changes.append(isc_prev)
                            if (
                                issue.status
                                and not getattr(issue.status, "final_status", False)
                                and not getattr(issue.status, "rejected_status", False)
                            ):
                                isc = create_isc_safe(
                                    issue=issue,
                                    status=issue.status,
                                    entered_at=issue.intake_date,
                                    exited_at=issue.resolution_date,
                                )
                                if isc:
                                    created_status_changes.append(isc)
                        combos_created += 1
                    if combos_created >= combos_limit:
                        break

        # Summary output
        self.stdout.write(self.style.SUCCESS(f"Created {len(created_issues)} test issues."))
        self.stdout.write(self.style.SUCCESS(f"Created {len(created_status_changes)} IssueStatusChange rows."))
        self.stdout.write(
            self.style.NOTICE(
                "Now run: python manage.py populate_performance_metrics --create-global --create-regions "
                "--create-categories --create-region-category --create-status-bottlenecks --limit-regions 10 --limit-categories 10"
            )
        )
