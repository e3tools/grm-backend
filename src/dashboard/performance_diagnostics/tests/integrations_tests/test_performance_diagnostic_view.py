from django.urls import reverse

from authentication.factories import UserFactory
from dashboard.constants import PERIOD_CHOICES
from grm.tests.base import DashboardTestCase
from issues.models import IssueCategory


class PerformanceDiagnosticsViewTest(DashboardTestCase):
    """Integration tests for the PerformanceDiagnosticsView (dashboard page)."""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.url = reverse("dashboard:performance_diagnostics:dashboard")

    def test_access_granted_for_grm_manager(self):
        """GRM Manager can access the performance diagnostics page"""
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200
        assert "performance_diagnostics/dashboard.html" in [t.name for t in resp.templates]

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot access the performance diagnostics page"""
        resp = self.get(self.url, user=self.normal_user)
        assert resp.status_code == 403

    def test_context_contains_form_categories_and_period_choices(self):
        """Context contains the search form, available_categories and period choices"""
        resp = self.get(self.url, user=self.manager)
        ctx = self.get_context(resp)

        # Basic presence checks
        assert "form" in ctx
        assert "available_categories" in ctx
        assert "period_choices" in ctx

        # period_choices should match the model constant shape
        model_periods = dict(PERIOD_CHOICES)
        resp_periods = dict(ctx["period_choices"])
        assert resp_periods.keys() == model_periods.keys()

    def test_available_categories_is_queryset_like(self):
        """available_categories is an iterable of IssueCategory instances (may be empty)"""
        resp = self.get(self.url, user=self.manager)
        ctx = self.get_context(resp)
        cats = ctx["available_categories"]
        # Must be iterable; if not empty, items should be IssueCategory instances
        assert hasattr(cats, "__iter__")
        if len(cats) > 0:
            assert isinstance(next(iter(cats)), IssueCategory)
