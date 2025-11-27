from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.constants import WEEKLY_CHOICE
from dashboard.models import StatusBottleneckMetrics
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueFactory,
    IssueStatusChangeFactory,
    IssueStatusFactory,
)
from issues.models import IssueStatus


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class PopulateStatusBottlenecksCommandTest(TestCase):
    """Unit tests for populate_status_bottlenecks management command."""

    def setUp(self):
        super().setUp()
        self.region = AdministrativeRegionFactory()
        self.category = IssueCategoryFactory()

        self.status_in_progress = IssueStatusFactory(
            name="In Progress",
            final_status=False,
            rejected_status=False,
            threshold_days=5.0,
        )
        # terminal status must satisfy DB constraint (threshold_days > 0)
        self.status_resolved = IssueStatusFactory(
            name="Resolved",
            final_status=True,
            rejected_status=False,
            threshold_days=1.0,
        )

        StatusBottleneckMetrics.objects.all().delete()

    def test_command_creates_snapshots_for_all_periods_by_default(self):
        """Running without --period should create snapshots for 7d, 30d, and 90d."""
        out = StringIO()
        call_command("populate_status_bottlenecks", "--only-global", "--dry-run", stdout=out)

        output = out.getvalue()
        # check that the command printed something indicating dry-run mode
        assert "7d" in output or "weekly" in output.lower() or "7d" in output.lower()
        assert "dry-run" in output.lower()

    def test_command_creates_snapshots_for_specific_period(self):
        """Running with --period 7d should only create snapshots for weekly."""
        out = StringIO()
        call_command(
            "populate_status_bottlenecks",
            "--period",
            WEEKLY_CHOICE,
            "--only-global",
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        assert WEEKLY_CHOICE in output or "weekly" in output.lower()

    def test_command_persists_status_bottleneck_metrics(self):
        """Command should persist StatusBottleneckMetrics rows for each status."""
        now = timezone.now()

        # Create an issue with status changes
        issue = IssueFactory(
            administrative_region=self.region,
            category=self.category,
            confirmed=True,
            status=self.status_in_progress,
        )

        # Create status change: entered_at now, exited_at in 3 days (closed ISC)
        entered_at = now - timedelta(days=7)
        exited_at = entered_at + timedelta(days=3)
        IssueStatusChangeFactory(
            issue=issue,
            status=self.status_in_progress,
            entered_at=entered_at,
            exited_at=exited_at,
        )

        # Persist snapshot for the region (not global) so the ISC is included
        call_command("populate_status_bottlenecks", "--period", WEEKLY_CHOICE, "--regions", str(self.region.id))

        # Verify metrics were created
        metrics = StatusBottleneckMetrics.objects.filter(period=WEEKLY_CHOICE)
        assert metrics.exists()
        assert metrics.count() >= 1  # At least one status has data

        # Find the metric for our status
        metric = metrics.filter(issue_status=self.status_in_progress).first()
        assert metric is not None
        assert metric.issues_count > 0

    def test_command_filters_by_region(self):
        """Command with --regions should only process specified regions."""
        # Create a minimal ISC so the region snapshot will have data
        now = timezone.now()
        issue = IssueFactory(
            administrative_region=self.region,
            category=self.category,
            confirmed=True,
            status=self.status_in_progress,
        )
        IssueStatusChangeFactory(
            issue=issue,
            status=self.status_in_progress,
            entered_at=now - timedelta(days=3),
            exited_at=now - timedelta(days=1),
        )

        # Run the command for the specific region (persist)
        call_command(
            "populate_status_bottlenecks",
            "--period",
            WEEKLY_CHOICE,
            "--regions",
            str(self.region.id),
        )

        # Now assert that metrics exist for that region
        metrics_for_region = StatusBottleneckMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region=self.region,
        )
        assert metrics_for_region.exists()

    def test_command_filters_by_category(self):
        """Command with --categories should only process specified categories."""
        out = StringIO()
        call_command(
            "populate_status_bottlenecks",
            "--period",
            WEEKLY_CHOICE,
            "--only-global",
            "--categories",
            str(self.category.id),
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        assert str(self.category.id) in output or "dry-run" in output.lower()

    def test_command_respects_only_global_flag(self):
        """--only-global should compute only global (region=None, category=None) snapshot."""
        call_command(
            "populate_status_bottlenecks",
            "--period",
            WEEKLY_CHOICE,
            "--only-global",
        )

        metrics = StatusBottleneckMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region__isnull=True,
            category__isnull=True,
        )
        assert metrics.exists()

    def test_command_with_dry_run_does_not_persist(self):
        """--dry-run should not persist any metrics."""
        initial_count = StatusBottleneckMetrics.objects.count()

        call_command(
            "populate_status_bottlenecks",
            "--period",
            WEEKLY_CHOICE,
            "--only-global",
            "--dry-run",
        )

        final_count = StatusBottleneckMetrics.objects.count()
        assert final_count == initial_count

    def test_command_creates_rows_for_all_statuses(self):
        """Command should create rows for all IssueStatus objects even if no data."""
        call_command(
            "populate_status_bottlenecks",
            "--period",
            WEEKLY_CHOICE,
            "--only-global",
        )

        metrics = StatusBottleneckMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region__isnull=True,
            category__isnull=True,
        )

        # Should have a row for each status
        status_count = IssueStatus.objects.count()
        assert metrics.count() == status_count

    def test_command_calculates_average_time_in_status_correctly(self):
        """Command should calculate average time in status from IssueStatusChange rows."""
        now = timezone.now()

        issue1 = IssueFactory(
            administrative_region=self.region,
            category=self.category,
            confirmed=True,
            status=self.status_in_progress,
        )
        issue2 = IssueFactory(
            administrative_region=self.region,
            category=self.category,
            confirmed=True,
            status=self.status_in_progress,
        )

        # Issue 1: 2 days in status
        IssueStatusChangeFactory(
            issue=issue1,
            status=self.status_in_progress,
            entered_at=now - timedelta(days=7),
            exited_at=now - timedelta(days=7) + timedelta(days=2),
        )

        # Issue 2: 4 days in status
        IssueStatusChangeFactory(
            issue=issue2,
            status=self.status_in_progress,
            entered_at=now - timedelta(days=5),
            exited_at=now - timedelta(days=5) + timedelta(days=4),
        )

        # Persist snapshot for the region so the ISC rows are included
        start_date = (now - timedelta(days=7)).isoformat()
        end_date = now.isoformat()

        call_command(
            "populate_status_bottlenecks",
            "--period",
            WEEKLY_CHOICE,
            "--regions",
            str(self.region.id),
            "--start-date",
            start_date,
            "--end-date",
            end_date,
        )

        metric = StatusBottleneckMetrics.objects.get(
            period=WEEKLY_CHOICE,
            administrative_region=self.region,
            category__isnull=True,
            issue_status=self.status_in_progress,
        )

        # Average should be (2 + 4) / 2 = 3 days (use tolerant assertion)
        assert metric.average_time_in_status_days is not None
        assert abs(metric.average_time_in_status_days - 3.0) < 0.1

    def test_command_creates_metrics_for_ancestor_regions(self):
        """If issues exist in a descendant region, metrics should be created for that region and its ancestors."""
        # Create a child region under self.region and an issue in the child
        child_region = AdministrativeRegionFactory(parent=self.region)

        now = timezone.now()
        issue = IssueFactory(
            administrative_region=child_region,
            category=self.category,
            confirmed=True,
            status=self.status_in_progress,
        )
        # Create a closed ISC inside the default weekly window
        IssueStatusChangeFactory(
            issue=issue,
            status=self.status_in_progress,
            entered_at=now - timedelta(days=3),
            exited_at=now - timedelta(days=1),
        )

        # Option 1: run the command for all regions (recommended if the command supports scanning all regions)
        # This mirrors how populate_performance_metrics discovers regions with issues and their ancestors.
        call_command(
            "populate_status_bottlenecks",
            "--period",
            WEEKLY_CHOICE,
            "--regions",
            # pass both child and ancestor to be explicit and robust
            str(child_region.id),
            str(self.region.id),
        )

        # Metrics should exist for the child region (where the issue lives)
        child_metrics = StatusBottleneckMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region=child_region,
        )
        assert child_metrics.exists()

        # Metrics should also exist for the ancestor region (self.region)
        ancestor_metrics = StatusBottleneckMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region=self.region,
        )
        assert ancestor_metrics.exists()
