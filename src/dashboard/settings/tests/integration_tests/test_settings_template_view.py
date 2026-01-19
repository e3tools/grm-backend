from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase


class SettingsTemplateViewTest(DashboardTestCase):
    """Tests for SettingsTemplateView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.url = reverse("dashboard:settings:main")

    def test_access_granted_for_grm_manager(self):
        """GRM Manager can access settings"""
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200
        assert "settings/main.html" in [t.name for t in resp.templates]

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot access settings"""
        resp = self.get(self.url, user=self.normal_user)
        assert resp.status_code == 403

    def test_context_data(self):
        """All user creation forms should be in context"""
        resp = self.get(self.url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["title"] == "Settings"
        assert ctx["active_level1"] == "settings"
