import pytest
from django.test import TestCase
from django.urls import reverse

from authentication.factories import UserFactory


@pytest.mark.django_db
class TestDisableWizardCacheMiddleware(TestCase):
    """Tests for DisableWizardCacheMiddleware."""

    def setUp(self):
        self.user = UserFactory()
        self.wizard_url = reverse("wizard:customization_wizard")
        self.dashboard_url = reverse("dashboard:diagnostics:home")

    def test_wizard_url_has_no_cache_headers(self):
        """Wizard URLs should include no-cache headers."""
        self.client.force_login(self.user)
        resp = self.client.get(self.wizard_url)

        assert resp.status_code == 404
        assert resp["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
        assert resp["Pragma"] == "no-cache"
        assert resp["Expires"] == "0"

    def test_non_wizard_url_has_normal_cache_headers(self):
        """Non-wizard URLs should not include no-cache headers."""
        self.client.force_login(self.user)
        resp = self.client.get(self.dashboard_url)

        assert resp.status_code == 404
        assert "Cache-Control" not in resp
        assert "Pragma" not in resp
        assert "Expires" not in resp

    def test_anonymous_user_wizard_url_no_cache(self):
        """Even for anonymous users, wizard URLs must disable caching."""
        resp = self.client.get(self.wizard_url)

        assert resp.status_code == 404
        assert resp["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
        assert resp["Pragma"] == "no-cache"
        assert resp["Expires"] == "0"
