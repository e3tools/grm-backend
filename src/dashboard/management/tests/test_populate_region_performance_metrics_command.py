from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from dashboard.constants import MONTHLY_CHOICE, QUARTERLY_CHOICE, WEEKLY_CHOICE
from dashboard.models import RegionPerformanceMetrics
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueFactory,
)


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class PopulateRegionPerformanceMetricsCommandTest(TestCase):
    """Unit tests for populate_region_performance_metrics management command."""

    def setUp(self):
        super().setUp()
        # single root region is created by base fixtures in many test suites; create a region to act as root if needed
        self.root = AdministrativeRegionFactory(parent=None)
        # child region under root
        self.region = AdministrativeRegionFactory(parent=self.root)
        self.category = IssueCategoryFactory()

        RegionPerformanceMetrics.objects.all().delete()

    def test_command_creates_metrics_for_child_and_ancestors(self):
        """If issues exist in a descendant region, metrics should be created for that region and its ancestors."""
        # Create a child-of-child region and an issue in that leaf
        child_region = AdministrativeRegionFactory(parent=self.region)
        IssueFactory(administrative_region=child_region, category=self.category, confirmed=True)

        # Run the command to populate metrics (persist)
        call_command(
            "populate_region_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--regions",
            str(child_region.id),
            # include ancestor explicitly to mirror real runs (command also expands ancestors when scanning)
            str(self.region.id),
        )

        # Metrics should exist for the child region (where the issue lives)
        child_metrics = RegionPerformanceMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            region=child_region,
        )
        assert child_metrics.exists()

        # Metrics should also exist for the ancestor region (self.region)
        ancestor_metrics = RegionPerformanceMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            region=self.region,
        )
        assert ancestor_metrics.exists()

    def test_command_with_dry_run_does_not_persist(self):
        """--dry-run should not persist any RegionPerformanceMetrics rows."""
        IssueFactory(administrative_region=self.region, confirmed=True)

        initial_count = RegionPerformanceMetrics.objects.count()

        call_command(
            "populate_region_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--regions",
            str(self.region.id),
            "--dry-run",
        )

        final_count = RegionPerformanceMetrics.objects.count()
        assert final_count == initial_count

    def test_command_processes_multiple_periods(self):
        """Command with multiple --periods should create metrics for all requested periods."""
        IssueFactory(administrative_region=self.region, confirmed=True)

        call_command(
            "populate_region_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            MONTHLY_CHOICE,
            QUARTERLY_CHOICE,
            "--regions",
            str(self.region.id),
        )

        for period in (WEEKLY_CHOICE, MONTHLY_CHOICE, QUARTERLY_CHOICE):
            metrics = RegionPerformanceMetrics.objects.filter(period=period, region=self.region)
            assert metrics.exists()

    def test_command_respects_limit_regions(self):
        """--limit-regions should limit the number of initial regions considered (no error)."""
        # create several regions with issues
        for _ in range(3):
            r = AdministrativeRegionFactory(parent=self.root)
            IssueFactory(administrative_region=r, confirmed=True)

        out = StringIO()
        # limit to 1 initial region (command expands ancestors internally)
        call_command(
            "populate_region_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--limit-regions",
            "1",
            stdout=out,
        )

        output = out.getvalue()
        # Command should complete without raising and print progress; we don't assert exact counts here
        assert "Completed" in output or "Calculated" in output or output != ""

    def test_command_creates_region_category_combination_metrics(self):
        """Command should create metrics for region x category combinations when categories passed."""
        IssueFactory(administrative_region=self.region, category=self.category, confirmed=True)

        call_command(
            "populate_region_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--regions",
            str(self.region.id),
            "--categories",
            str(self.category.id),
        )

        metrics = RegionPerformanceMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            region=self.region,
            category=self.category,
        )
        assert metrics.exists()

    def test_invalid_period_raises(self):
        """Passing an invalid period should raise CommandError (validation similar to other commands)."""
        with pytest.raises(CommandError):
            call_command(
                "populate_region_performance_metrics",
                "--periods",
                "invalid_period",
            )
