"""
Backfill IssueStatusChange rows from existing Issue data.

This command is conservative and idempotent by default:
 - It only processes confirmed issues.
 - It will not create duplicate IssueStatusChange rows if they already exist,
   unless --force-rebuild is passed.
 - It will close open IssueStatusChange rows using resolution_date when available.

Usage examples:
  # Dry-run to see what would be done
  python manage.py backfill_status_changes --dry-run

  # Run for all confirmed issues in batches of 500
  python manage.py backfill_status_changes --batch-size 500

  # Force rebuild (delete existing IssueStatusChange rows for processed issues first)
  python manage.py backfill_status_changes --force-rebuild --limit 1000
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from issues.models import Issue, IssueStatusChange


class Command(BaseCommand):
    help = "Backfill IssueStatusChange rows from existing Issue data (confirmed issues only)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simulate changes without writing to DB.')
        parser.add_argument('--batch-size', type=int, default=500, help='Number of issues to process per batch.')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of issues to process (0 = all).')
        parser.add_argument('--offset', type=int, default=0, help='Offset for sharding/backfill windows.')
        parser.add_argument(
            '--force-rebuild',
            action='store_true',
            help='Delete existing IssueStatusChange rows for processed issues before creating new ones.',
        )
        parser.add_argument('--start-id', type=int, default=None, help='Only process issues with id >= START_ID.')
        parser.add_argument('--end-id', type=int, default=None, help='Only process issues with id <= END_ID.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        limit = options['limit']
        offset = options['offset']
        force_rebuild = options['force_rebuild']
        start_id = options['start_id']
        end_id = options['end_id']

        qs = Issue.objects.filter(confirmed=True).order_by('id')

        if start_id is not None:
            qs = qs.filter(id__gte=start_id)
        if end_id is not None:
            qs = qs.filter(id__lte=end_id)
        if offset:
            qs = qs[offset:]
        if limit and limit > 0:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(self.style.NOTICE(f"Backfill starting. Confirmed issues to process: {total}"))

        processed = 0
        created_rows = 0
        updated_rows = 0
        skipped = 0

        # iterate in batches
        start_index = 0
        while start_index < total:
            batch = list(qs[start_index : start_index + batch_size])
            if not batch:
                break

            issue_ids = [i.id for i in batch]

            # Optionally delete existing IssueStatusChange rows for these issues
            if force_rebuild:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Dry-run: would delete IssueStatusChange rows for issues {issue_ids[:5]}..."
                        )
                    )
                else:
                    IssueStatusChange.objects.filter(issue_id__in=issue_ids).delete()
                    self.stdout.write(
                        self.style.NOTICE(
                            f"Deleted existing IssueStatusChange rows for batch starting at index {start_index}"
                        )
                    )

            # Preload existing status_changes for idempotency checks
            existing_map = {}
            existing_qs = IssueStatusChange.objects.filter(issue_id__in=issue_ids)
            for sc in existing_qs:
                existing_map.setdefault(sc.issue_id, []).append(sc)

            to_create = []
            to_update = []

            for issue in batch:
                processed += 1
                # If there are existing rows and not force_rebuild, skip creating duplicates
                existing = existing_map.get(issue.id, [])

                # Helper to find open change
                open_change = None
                for sc in existing:
                    if sc.exited_at is None:
                        open_change = sc
                        break

                # Determine current status and whether it's terminal
                status = getattr(issue, 'status', None)
                status_is_terminal = False
                if status:
                    status_is_terminal = bool(
                        getattr(status, 'final_status', False) or getattr(status, 'rejected_status', False)
                    )

                # If issue already has at least one change and not force_rebuild, we skip creating a new initial row.
                if existing and not force_rebuild:
                    # But we still may need to close an open change using resolution_date
                    if open_change and issue.resolution_date:
                        # If open_change.exited_at is null and resolution_date is present, close it
                        if open_change.exited_at is None:
                            if dry_run:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"Dry-run: would set exited_at for IssueStatusChange id={open_change.id} to {issue.resolution_date}"
                                    )
                                )
                            else:
                                open_change.exited_at = issue.resolution_date
                                to_update.append(open_change)
                                updated_rows += 1
                    else:
                        skipped += 1
                    continue

                # No existing rows or force_rebuild: create initial row if current status is not terminal
                if status and not status_is_terminal:
                    # Choose entered_at: prefer intake_date, fallback to created_date, fallback to now
                    entered_at = (
                        getattr(issue, 'intake_date', None) or getattr(issue, 'created_date', None) or timezone.now()
                    )
                    # If resolution_date exists and is earlier than entered_at, ignore resolution_date for this row
                    exited_at = None
                    if getattr(issue, 'resolution_date', None):
                        # If resolution_date > entered_at, we could set exited_at to resolution_date (issue resolved after being in this status)
                        if issue.resolution_date > entered_at:
                            exited_at = issue.resolution_date
                        else:
                            exited_at = None

                    # Create IssueStatusChange row
                    isc = IssueStatusChange(issue=issue, status=status, entered_at=entered_at, exited_at=exited_at)
                    if dry_run:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Dry-run: would create IssueStatusChange for issue_id={issue.id} status={status.name} entered_at={entered_at} exited_at={exited_at}"
                            )
                        )
                    else:
                        to_create.append(isc)
                        created_rows += 1
                else:
                    # status is terminal or missing: we do not create a new change row for terminal statuses.
                    # But if there is an open change (shouldn't be if no existing rows), close it using resolution_date if present.
                    if open_change and issue.resolution_date:
                        if dry_run:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Dry-run: would set exited_at for IssueStatusChange id={open_change.id} to {issue.resolution_date}"
                                )
                            )
                        else:
                            open_change.exited_at = issue.resolution_date
                            to_update.append(open_change)
                            updated_rows += 1
                    else:
                        skipped += 1

            # Bulk create and bulk update
            if to_create and not dry_run:
                IssueStatusChange.objects.bulk_create(to_create, batch_size=1000)
            if to_update and not dry_run:
                for obj in to_update:
                    obj.save(update_fields=['exited_at'])

            start_index += batch_size

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill completed. processed={processed}, created_rows={created_rows}, updated_rows={updated_rows}, skipped={skipped}"
            )
        )
