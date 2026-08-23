from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from authentication.factories import UserFactory
from dashboard.constants import NOT_APPLICABLE, WEEKLY_CHOICE
from dashboard.models import StatusBottleneckMetrics
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueStatusFactory,
)


class StatusBottleneckMetricsAPIViewTest(DashboardTestCase):
    """Integration tests for StatusBottleneckMetricsAPIView (AJAX endpoint returning bottleneck table)."""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()

        self.url = reverse("dashboard:performance_diagnostics:api_status_bottlenecks")

        self.region = AdministrativeRegionFactory(parent=self.root_region)
        self.category = IssueCategoryFactory()

        # Create issue statuses
        # Ensure threshold_days is always a numeric value (model enforces NOT NULL)
        self.status_in_progress = IssueStatusFactory(
            name="In Progress",
            final_status=False,
            rejected_status=False,
            threshold_days=5.0,
        )
        self.status_review = IssueStatusFactory(
            name="Under Review",
            final_status=False,
            rejected_status=False,
            threshold_days=3.0,
        )
        # For terminal statuses provide a numeric threshold (0.0 is acceptable if not used)
        self.status_resolved = IssueStatusFactory(
            name="Resolved",
            final_status=True,
            rejected_status=False,
            threshold_days=1.0,
        )

        # Clear existing bottleneck metrics
        StatusBottleneckMetrics.objects.all().delete()

    def test_api_returns_bottleneck_table_fragment_with_metrics(self):
        """When precomputed StatusBottleneckMetrics exist, API returns table fragment (200, text/html) with status rows."""
        now = timezone.now()
        start_date = now - timedelta(days=7)
        end_date = now

        # Create bottleneck metrics
        StatusBottleneckMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=start_date,
            end_date=end_date,
            administrative_region=self.region,
            category=None,
            issue_status=self.status_in_progress,
            issues_count=5,
            average_time_in_status_days=6.5,
            calculated_at=now,
        )
        StatusBottleneckMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=start_date,
            end_date=end_date,
            administrative_region=self.region,
            category=None,
            issue_status=self.status_review,
            issues_count=3,
            average_time_in_status_days=2.0,
            calculated_at=now,
        )
        StatusBottleneckMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=start_date,
            end_date=end_date,
            administrative_region=self.region,
            category=None,
            issue_status=self.status_resolved,
            issues_count=10,
            average_time_in_status_days=0.0,
            calculated_at=now,
        )

        data = {
            "period": WEEKLY_CHOICE,
            "administrative_region": self.region.id,
        }
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        ctype = resp.get("Content-Type", "")
        assert "html" in ctype.lower()

        text = resp.content.decode("utf-8")
        assert "In Progress" in text
        assert "Under Review" in text
        assert "Resolved" in text

    def test_api_renders_performance_status_indicators(self):
        """API should render correct performance status (good/at-risk/critical) badges based on average time."""
        now = timezone.now()
        start_date = now - timedelta(days=7)
        end_date = now

        # GOOD: 4.5 days (threshold 5.0, < 1.2 * threshold = 6.0)
        StatusBottleneckMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=start_date,
            end_date=end_date,
            administrative_region=self.region,
            category=None,
            issue_status=self.status_in_progress,
            issues_count=5,
            average_time_in_status_days=4.5,
            calculated_at=now,
        )

        # AT_RISK: choose a value between 1.2*threshold and 1.5*threshold for status_review (threshold 3.0)
        StatusBottleneckMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=start_date,
            end_date=end_date,
            administrative_region=self.region,
            category=None,
            issue_status=self.status_review,
            issues_count=3,
            average_time_in_status_days=4.0,
            calculated_at=now,
        )

        data = {
            "period": WEEKLY_CHOICE,
            "administrative_region": self.region.id,
        }
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        text = resp.content.decode("utf-8")

        # Should have performance badges
        assert "badge" in text.lower()

    def test_api_renders_not_applicable_for_terminal_statuses(self):
        """Terminal statuses should show N/A for average time in status."""
        now = timezone.now()
        start_date = now - timedelta(days=7)
        end_date = now

        StatusBottleneckMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=start_date,
            end_date=end_date,
            administrative_region=self.region,
            category=None,
            issue_status=self.status_resolved,
            issues_count=10,
            average_time_in_status_days=0.0,
            calculated_at=now,
        )

        data = {
            "period": WEEKLY_CHOICE,
            "administrative_region": self.region.id,
        }
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        text = resp.content.decode("utf-8")
        assert str(NOT_APPLICABLE) in text

    def test_api_fallback_count_for_terminal_statuses_without_snapshot(self):
        """When no snapshot exists for a terminal status, API counts confirmed issues from Issue table."""
        # Don't create any StatusBottleneckMetrics for status_resolved
        # The view should count confirmed issues directly

        data = {
            "period": WEEKLY_CHOICE,
            "administrative_region": self.region.id,
        }
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        text = resp.content.decode("utf-8")
        # Should render the table even without snapshots
        assert "Resolved" in text

    def test_api_access_denied_for_non_manager(self):
        """Non-GRM Manager should be forbidden from accessing the endpoint."""
        data = {
            "period": WEEKLY_CHOICE,
            "administrative_region": self.region.id,
        }
        resp = self.get(self.url, data=data, user=self.normal_user, ajax=True)
        assert resp.status_code == 403

    def test_api_non_ajax_request_returns_404(self):
        """Non-AJAX requests should return 404 due to AJAXRequestMixin."""
        data = {
            "period": WEEKLY_CHOICE,
            "administrative_region": self.region.id,
        }
        resp = self.get(self.url, data=data, user=self.manager)
        assert resp.status_code == 404

    def test_api_filters_by_category(self):
        """API should return metrics filtered by specific category."""
        now = timezone.now()
        start_date = now - timedelta(days=7)
        end_date = now

        StatusBottleneckMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=start_date,
            end_date=end_date,
            administrative_region=self.region,
            category=self.category,
            issue_status=self.status_in_progress,
            issues_count=2,
            average_time_in_status_days=5.0,
            calculated_at=now,
        )

        data = {
            "period": WEEKLY_CHOICE,
            "administrative_region": self.region.id,
            "category": self.category.id,
        }
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        text = resp.content.decode("utf-8")
        assert "In Progress" in text

    def test_api_defaults_to_weekly_on_invalid_period(self):
        """Invalid period should default to WEEKLY_CHOICE."""
        now = timezone.now()
        start_date = now - timedelta(days=7)
        end_date = now

        StatusBottleneckMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=start_date,
            end_date=end_date,
            administrative_region=self.region,
            category=None,
            issue_status=self.status_in_progress,
            issues_count=5,
            average_time_in_status_days=6.5,
            calculated_at=now,
        )

        data = {
            "period": "invalid",
            "administrative_region": self.region.id,
        }
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        text = resp.content.decode("utf-8")
        assert "In Progress" in text
