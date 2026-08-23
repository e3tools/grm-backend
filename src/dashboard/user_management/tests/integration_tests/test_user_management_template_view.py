from django.urls import reverse

from authentication.factories import UserFactory
from dashboard.user_management.constants import FACILITATOR_CHOICE, GRM_MANAGER_CHOICE
from grm.tests.base import DashboardTestCase


class UserManagementTemplateViewTest(DashboardTestCase):
    """Tests for UserManagementTemplateView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.url = reverse("dashboard:user_management:home")

    def test_access_granted_for_grm_manager(self):
        """GRM Manager can access user management"""
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200
        assert "user_management/user_management.html" in [t.name for t in resp.templates]

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot access user management"""
        resp = self.get(self.url, user=self.normal_user)
        assert resp.status_code == 403

    def test_default_tab_is_grm_manager(self):
        """Default active tab should be GRM Manager"""
        resp = self.get(self.url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["active_tab"] == GRM_MANAGER_CHOICE

    def test_active_tab_from_url_parameter(self):
        """Active tab should be set from URL parameter"""
        resp = self.get(f"{self.url}?tab={FACILITATOR_CHOICE}", user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["active_tab"] == FACILITATOR_CHOICE

    def test_invalid_tab_defaults_to_grm_manager(self):
        """Invalid tab parameter should default to GRM Manager"""
        resp = self.get(f"{self.url}?tab=invalid_tab", user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["active_tab"] == GRM_MANAGER_CHOICE

    def test_forms_present_in_context(self):
        """All user creation forms should be in context"""
        resp = self.get(self.url, user=self.manager)
        ctx = self.get_context(resp)
        assert "grm_manager_form" in ctx
        assert "case_manager_form" in ctx
        assert "facilitator_form" in ctx
