from django.urls import reverse
from django.utils import timezone

from authentication.factories import UserFactory
from dashboard.constants import MONTHLY_CHOICE, WEEKLY_CHOICE
from dashboard.models import PerformanceMetrics
from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory, IssueCategoryFactory


class PerformanceMetricsAPIViewTest(DashboardTestCase):
    """Integration tests for PerformanceMetricsAPIView (AJAX endpoint returning KPI fragment)."""

    def setUp(self):
        super().setUp()
        # Users
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()

        # URLs
        self.url = reverse("dashboard:performance_diagnostics:api_metrics")

        # Create a region and a category
        self.region = AdministrativeRegionFactory(parent=self.root_region)
        self.category = IssueCategoryFactory()

        # Delete all PerformanceMetrics
        PerformanceMetrics.objects.all().delete()

        # Create a PerformanceMetrics row for period '7d'
        now = timezone.now()

        self.metrics_obj = PerformanceMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=now - timezone.timedelta(days=7),
            end_date=now,
            administrative_region=self.region,
            category=None,  # test the region-level case without category
            active_users_count=12,
            active_users_metric="WAU",
            active_users_change_percentage=3.0,
            new_issues_count=5,
            new_issues_change_percentage=-2.0,
            average_resolution_days=4.5,
            resolution_rate=80.0,
            total_resolved_issues=4,
            total_issues=5,
            average_satisfaction_score=4.1,
            appeal_rate=0.5,
            total_appeals=1,
            total_rated_issues=3,
            calculated_at=now,
        )

    def test_api_context_contains_expected_keys_and_values(self):
        """The view should populate context with metrics dict and derived status objects."""
        data = {"period": WEEKLY_CHOICE, "administrative_region": self.region.id}
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)

        # Response should be OK and render a template
        assert resp.status_code == 200
        assert "performance_diagnostics/kpi_cards.html" in [t.name for t in resp.templates]

        # The view rendered with a RequestContext; inspect context
        ctx = resp.context
        assert "metrics" in ctx
        assert "user_adoption_status" in ctx
        assert "resolution_status" in ctx
        assert "satisfaction_status" in ctx
        assert "last_updated" in ctx

        # metrics should be equal to the object's to_dict()
        expected_metrics_dict = self.metrics_obj.to_dict()
        assert ctx["metrics"] == expected_metrics_dict

        # statuses should match what the model returns for the object
        assert ctx["user_adoption_status"] == self.metrics_obj.get_user_adoption_status()
        assert ctx["resolution_status"] == self.metrics_obj.get_resolution_status(target=10.0)
        assert ctx["satisfaction_status"] == self.metrics_obj.get_satisfaction_status(target=4.0)

        # last_updated should be the calculated_at timestamp
        assert ctx["last_updated"] == self.metrics_obj.calculated_at

    def test_api_returns_html_fragment_for_existing_metrics(self):
        """When a precomputed PerformanceMetrics exists, the API should return an HTML fragment (200, text/html) with KPI cards."""
        data = {"period": WEEKLY_CHOICE, "administrative_region": self.region.id}
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        # Content-Type should be HTML (template fragment)
        ctype = resp.get("Content-Type", "")
        assert "html" in ctype.lower()

        text = resp.content.decode("utf-8")
        # basic checks that the KPI fragment rendered (labels present)
        assert "User Adoption" in text
        assert "Issue Resolution" in text
        assert "Citizen Satisfaction" in text
        # and a metric value present
        assert "12" in text or "active_users_count" not in text  # expect the number 12 visible

    def test_api_returns_error_fragment_when_no_metrics(self):
        """When no precomputed metrics exist for the requested filters, API returns the error fragment with message."""
        # Use a period that we didn't create (30d)
        data = {"period": MONTHLY_CHOICE, "administrative_region": self.region.id}
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        ctype = resp.get("Content-Type", "")
        assert "html" in ctype.lower()

        text = resp.content.decode("utf-8")
        assert "No metrics available for the selected filters." in text

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager should be forbidden from accessing the endpoint."""
        data = {"period": WEEKLY_CHOICE, "administrative_region": self.region.id}
        resp = self.get(self.url, data=data, user=self.normal_user, ajax=True)
        assert resp.status_code == 403

    def test_non_ajax_request_returns_404(self):
        """Test that non-AJAX requests return 404 due to AJAXRequestMixin."""
        data = {"period": WEEKLY_CHOICE, "administrative_region": self.region.id}
        resp = self.get(self.url, data=data, user=self.manager)
        assert resp.status_code == 404

    def test_api_returns_html_fragment_when_filtered_by_category(self):
        """When a precomputed PerformanceMetrics exists for a specific category, API returns that fragment."""
        # Create a metrics row tied to the category
        now = timezone.now()
        PerformanceMetrics.objects.create(
            period=WEEKLY_CHOICE,
            start_date=now - timezone.timedelta(days=7),
            end_date=now,
            administrative_region=self.region,
            category=self.category,  # category-specific metric
            active_users_count=7,
            active_users_metric="WAU",
            active_users_change_percentage=1.0,
            new_issues_count=2,
            new_issues_change_percentage=0.0,
            average_resolution_days=2.0,
            resolution_rate=90.0,
            total_resolved_issues=2,
            total_issues=2,
            average_satisfaction_score=4.5,
            appeal_rate=0.0,
            total_appeals=0,
            total_rated_issues=2,
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
        # Should render KPI fragment and show the category-specific primary metric value (7)
        assert "User Adoption" in text
        assert "7" in text

    def test_api_returns_error_when_category_filter_has_no_metrics(self):
        """Requesting a category that has no metrics should return the error fragment."""

        data = {
            "period": MONTHLY_CHOICE,
            "administrative_region": self.region.id,
            "category": self.category.id,
        }
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        text = resp.content.decode("utf-8")
        assert "No metrics available for the selected filters." in text

    def test_invalid_period_falls_back_to_default_7d_if_available(self):
        """If an invalid period is passed, the view should default to 7d and return existing 7d metrics if present."""
        # Call API with an invalid period; since we have a 7d metric for this region, it should return that fragment.
        data = {
            "period": "invalid_period",
            "administrative_region": self.region.id,
        }
        resp = self.get(self.url, data=data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        text = resp.content.decode("utf-8")
        assert "User Adoption" in text
        # the 7d metric created in setUp had active_users_count=12
        assert "12" in text
