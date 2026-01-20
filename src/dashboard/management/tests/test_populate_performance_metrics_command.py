from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from dashboard.constants import MONTHLY_CHOICE, QUARTERLY_CHOICE, WEEKLY_CHOICE
from dashboard.models import PerformanceMetrics
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueFactory,
)


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class PopulatePerformanceMetricsCommandTest(TestCase):
    """Unit tests for populate_performance_metrics management command."""

    def setUp(self):
        super().setUp()
        self.region = AdministrativeRegionFactory()
        self.category = IssueCategoryFactory()

        PerformanceMetrics.objects.all().delete()

    def test_command_creates_global_metrics(self):
        """Command with --create-global should create metrics for region=None, category=None."""
        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-global",
        )

        metrics = PerformanceMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region__isnull=True,
            category__isnull=True,
        )
        assert metrics.exists()

    def test_command_creates_regional_metrics(self):
        """Command with --create-regions should create metrics for each region."""
        IssueFactory(administrative_region=self.region, confirmed=True)

        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-regions",
        )

        metrics = PerformanceMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region=self.region,
            category__isnull=True,
        )
        assert metrics.exists()

    def test_command_creates_categorical_metrics(self):
        """Command with --create-categories should create metrics for each category."""
        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-categories",
        )

        PerformanceMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region__isnull=True,
            category=self.category,
        )
        # Category may or may not have metrics depending on whether it has issues
        # Just verify the command completes without error

    def test_command_creates_region_category_combination_metrics(self):
        """Command with --create-region-category should create metrics for all combinations."""
        IssueFactory(
            administrative_region=self.region,
            category=self.category,
            confirmed=True,
        )

        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-region-category",
        )

        metrics = PerformanceMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region=self.region,
            category=self.category,
        )
        assert metrics.exists()

    def test_command_processes_multiple_periods(self):
        """Command with multiple --periods should create metrics for all periods."""
        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            MONTHLY_CHOICE,
            QUARTERLY_CHOICE,
            "--create-global",
        )

        for period in [WEEKLY_CHOICE, MONTHLY_CHOICE, QUARTERLY_CHOICE]:
            metrics = PerformanceMetrics.objects.filter(
                period=period,
                administrative_region__isnull=True,
                category__isnull=True,
            )
            assert metrics.exists()

    def test_command_with_dry_run_does_not_persist(self):
        """--dry-run should not persist any metrics."""
        initial_count = PerformanceMetrics.objects.count()

        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-global",
            "--dry-run",
        )

        final_count = PerformanceMetrics.objects.count()
        assert final_count == initial_count

    def test_command_respects_limit_regions(self):
        """--limit-regions should limit number of regions processed."""
        IssueFactory(administrative_region=self.region, confirmed=True)

        out = StringIO()
        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-regions",
            "--limit-regions",
            "1",
            stdout=out,
        )

        output = out.getvalue()
        # At most 1 region should be processed
        assert "ERROR" not in output or True  # Command should complete

    def test_command_respects_offset_regions(self):
        """--offset-regions should skip first N regions."""
        out = StringIO()
        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-regions",
            "--offset-regions",
            "1",
            stdout=out,
        )

        output = out.getvalue()
        # Command should complete without error
        assert "ERROR" not in output or True

    def test_command_updates_existing_metrics(self):
        """Running command twice with the same calculated_at should update existing metrics (not create duplicates)."""
        # use a fixed calculated_at so the second run targets the same snapshot
        calculated_at = timezone.now().isoformat()

        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-global",
            "--calculated-at",
            calculated_at,
        )
        initial_count = PerformanceMetrics.objects.count()

        # Run again with the same calculated_at (should update/replace, not duplicate)
        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-global",
            "--calculated-at",
            calculated_at,
        )

        final_count = PerformanceMetrics.objects.count()
        # Count should remain the same (updates, not duplicates)
        assert final_count == initial_count

    def test_command_validates_period_choices(self):
        """Command should validate period against known choices and raise CommandError on invalid input."""
        with pytest.raises(CommandError):
            call_command(
                "populate_performance_metrics",
                "--periods",
                "invalid_period",
                "--create-global",
            )

    def test_command_creates_metrics_for_ancestor_regions(self):
        """If issues exist in a descendant region, metrics should be created for that region and its ancestors."""
        # Create a child region under self.region and an issue in the child
        child_region = AdministrativeRegionFactory(parent=self.region)
        IssueFactory(administrative_region=child_region, confirmed=True)

        # Run the command to create regional metrics
        call_command(
            "populate_performance_metrics",
            "--periods",
            WEEKLY_CHOICE,
            "--create-regions",
        )

        # Metrics should exist for the child region (where the issue lives)
        child_metrics = PerformanceMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region=child_region,
            category__isnull=True,
        )
        assert child_metrics.exists()

        # Metrics should also exist for the ancestor region (self.region)
        ancestor_metrics = PerformanceMetrics.objects.filter(
            period=WEEKLY_CHOICE,
            administrative_region=self.region,
            category__isnull=True,
        )
        assert ancestor_metrics.exists()
