from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from authentication.factories import GovernmentWorkerFactory
from dashboard.constants import WEEKLY_CHOICE
from dashboard.models import RegionPerformanceMetrics
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueFactory,
)
from issues.models import IssueStatus


class RegionPerformanceMetricsTest(TestCase):
    """Unit tests for RegionPerformanceMetrics model calculations."""

    def setUp(self):
        self.region = AdministrativeRegionFactory()
        self.category = IssueCategoryFactory()

    def test_calculate_data_creates_metric_object(self):
        """Calling calculate_data and persisting should create or update a metric."""
        IssueFactory(
            administrative_region=self.region,
            category=self.category,
            confirmed=True,
        )

        data = RegionPerformanceMetrics.calculate_data(
            region=self.region, category=self.category, period=WEEKLY_CHOICE, days=7
        )

        # Persist the returned data into the model (mimic previous calculate_for_region behavior)
        metric, _ = RegionPerformanceMetrics.objects.update_or_create(
            region=self.region,
            category=self.category,
            period=WEEKLY_CHOICE,
            defaults={
                'open_issues_count': data.get('open_issues_count', 0),
                'avg_resolution_days': data.get('avg_resolution_days'),
                'active_workers_count': data.get('active_workers_count', 0),
                'total_workers_in_region': data.get('total_workers_in_region', 0),
                'open_issues_score': data.get('open_issues_score', 0.0),
                'resolution_score': data.get('resolution_score', 0.0),
                'active_workers_score': data.get('active_workers_score', 0.0),
                'overall_performance_score': data.get('overall_performance_score', 0.0),
                'calculated_at': data.get('calculated_at'),
            },
        )

        assert metric.id is not None
        assert metric.region == self.region
        assert metric.category == self.category
        assert metric.period == WEEKLY_CHOICE

    def test_open_issues_count_excludes_resolved_and_rejected(self):
        """Open issues should exclude resolved and rejected statuses."""
        status_resolved = IssueStatus.objects.create(name="Resolved", final_status=True, rejected_status=False)
        status_rejected = IssueStatus.objects.create(name="Rejected", final_status=False, rejected_status=True)
        status_open = IssueStatus.objects.create(name="Open", final_status=False, rejected_status=False)

        # Create issues
        IssueFactory(administrative_region=self.region, confirmed=True, status=status_open)
        IssueFactory(administrative_region=self.region, confirmed=True, status=status_open)
        IssueFactory(administrative_region=self.region, confirmed=True, status=status_resolved)
        IssueFactory(administrative_region=self.region, confirmed=True, status=status_rejected)

        data = RegionPerformanceMetrics.calculate_data(region=self.region, category=None, period=WEEKLY_CHOICE, days=7)

        assert data['open_issues_count'] == 2

    def test_average_resolution_time_calculated_from_resolved_issues(self):
        """Avg resolution should be calculated from resolved issues only."""
        status_resolved = IssueStatus.objects.create(name="Resolved", final_status=True, rejected_status=False)

        now = timezone.now()
        IssueFactory(
            administrative_region=self.region,
            confirmed=True,
            status=status_resolved,
            intake_date=now - timedelta(days=5),
            resolution_date=now,
        )
        IssueFactory(
            administrative_region=self.region,
            confirmed=True,
            status=status_resolved,
            intake_date=now - timedelta(days=3),
            resolution_date=now,
        )

        data = RegionPerformanceMetrics.calculate_data(region=self.region, category=None, period=WEEKLY_CHOICE, days=7)

        # Average should be (5 + 3) / 2 = 4 days (tolerant)
        avg = data.get('avg_resolution_days')
        assert avg is not None
        assert 3.9 <= avg <= 4.1

    def test_performance_status_good_for_high_score(self):
        """Performance status should be Good for score >= 70."""
        metric = RegionPerformanceMetrics(region=self.region, overall_performance_score=75.0)

        status = metric.get_performance_status()
        assert status['status'] == 'good'
        assert status['badge_class'] == 'badge-primary'

    def test_performance_status_at_risk_for_medium_score(self):
        """Performance status should be At Risk for 40 <= score < 70."""
        metric = RegionPerformanceMetrics(region=self.region, overall_performance_score=55.0)

        status = metric.get_performance_status()
        assert status['status'] == 'at_risk'
        assert status['badge_class'] == 'badge-warning'

    def test_performance_status_critical_for_low_score(self):
        """Performance status should be Critical for score < 40."""
        metric = RegionPerformanceMetrics(region=self.region, overall_performance_score=25.0)

        status = metric.get_performance_status()
        assert status['status'] == 'critical'
        assert status['badge_class'] == 'badge-danger'

    def test_color_coding_open_issues(self):
        """Open issues should use correct color: Green (<20), Amber (20-50), Red (>50)."""
        metric_green = RegionPerformanceMetrics(region=self.region, open_issues_count=15)
        assert metric_green.get_open_issues_color() == 'primary'

        metric_amber = RegionPerformanceMetrics(region=self.region, open_issues_count=35)
        assert metric_amber.get_open_issues_color() == 'warning'

        metric_red = RegionPerformanceMetrics(region=self.region, open_issues_count=75)
        assert metric_red.get_open_issues_color() == 'danger'

    def test_color_coding_resolution_time(self):
        """Resolution time should use correct color: Green (<7), Amber (7-15), Red (>15)."""
        metric_green = RegionPerformanceMetrics(region=self.region, avg_resolution_days=5.0)
        assert metric_green.get_resolution_time_color() == 'primary'

        metric_amber = RegionPerformanceMetrics(region=self.region, avg_resolution_days=10.0)
        assert metric_amber.get_resolution_time_color() == 'warning'

        metric_red = RegionPerformanceMetrics(region=self.region, avg_resolution_days=20.0)
        assert metric_red.get_resolution_time_color() == 'danger'

    def test_calculate_data_aggregates_descendants(self):
        """calculate_data should include issues and workers from region descendants."""
        # create a parent and two child regions
        parent = AdministrativeRegionFactory(parent=self.region, name="Parent")
        child_a = AdministrativeRegionFactory(parent=parent, name="Child A")
        child_b = AdministrativeRegionFactory(parent=parent, name="Child B")

        # create issues in children
        IssueFactory(administrative_region=child_a, confirmed=True)
        IssueFactory(administrative_region=child_b, confirmed=True)
        # create a worker in a child
        GovernmentWorkerFactory(administrative_region=child_a, user__last_login=timezone.now())

        data = RegionPerformanceMetrics.calculate_data(region=parent, category=None, period=WEEKLY_CHOICE, days=7)

        # Persist to model to reuse helper accessors if needed
        metric, _ = RegionPerformanceMetrics.objects.update_or_create(
            region=parent,
            category=None,
            period=WEEKLY_CHOICE,
            defaults={
                'open_issues_count': data.get('open_issues_count', 0),
                'avg_resolution_days': data.get('avg_resolution_days'),
                'active_workers_count': data.get('active_workers_count', 0),
                'total_workers_in_region': data.get('total_workers_in_region', 0),
                'open_issues_score': data.get('open_issues_score', 0.0),
                'resolution_score': data.get('resolution_score', 0.0),
                'active_workers_score': data.get('active_workers_score', 0.0),
                'overall_performance_score': data.get('overall_performance_score', 0.0),
                'calculated_at': data.get('calculated_at'),
            },
        )

        # Expect open_issues_count >= 2 (the two created)
        assert metric.open_issues_count >= 2
        # Expect active_workers_count >= 1 (the worker created)
        assert metric.active_workers_count >= 1
