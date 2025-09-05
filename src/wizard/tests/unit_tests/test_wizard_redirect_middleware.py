import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from dashboard.grm.constants import COMPLETE_CHOICE
from wizard.models import WizardSession

User = get_user_model()


@pytest.mark.django_db
class TestWizardRedirectMiddleware:
    @pytest.fixture
    def user(self):
        return User.objects.create_user(username="tester", password="pass123")

    def test_login_url_is_accessible_for_unauthenticated_user(self, client):
        """Login page should never redirect to wizard when unauthenticated."""
        resp = client.get(reverse("dashboard:authentication:login"))
        assert resp.status_code == 200  # middleware lets it pass

    def test_login_url_redirect_to_wizard_for_authenticated_user_if_wizard_incomplete(self, client, user):
        """Login page should redirect to wizard if wizard is missing or incomplete."""
        client.force_login(user)
        resp = client.get(reverse("dashboard:authentication:login"))
        assert resp.status_code == 302
        assert resp.url == reverse("dashboard:diagnostics:home")
        resp = client.get(reverse("dashboard:diagnostics:home"))
        assert resp.status_code == 302
        assert resp.url == reverse("dashboard:wizard:customization_wizard")

    def test_wizard_url_is_accessible(self, client, user):
        """Customization wizard page should be accessible when authenticated."""
        client.force_login(user)
        resp = client.get(reverse("dashboard:wizard:customization_wizard"))
        assert resp.status_code == 200  # middleware lets it pass

    def test_other_url_redirects_if_wizard_incomplete(self, client, user):
        """Other dashboard URLs should redirect to wizard if wizard is missing or incomplete."""
        client.force_login(user)

        # No WizardSession created yet → considered incomplete
        resp = client.get(reverse("dashboard:diagnostics:home"))
        assert resp.status_code == 302
        assert resp.url == reverse("dashboard:wizard:customization_wizard")

    def test_other_url_allowed_if_wizard_complete(self, client, user):
        """If wizard is complete, user should access dashboard URLs normally."""
        client.force_login(user)
        WizardSession.update_state(COMPLETE_CHOICE)

        resp = client.get(reverse("dashboard:diagnostics:home"))
        # Must not redirect to wizard
        assert resp.status_code == 200

    def test_urls_outside_dashboard_are_not_restricted(self, client, user):
        """Middleware should not enforce wizard on non-dashboard apps."""
        client.force_login(user)
        WizardSession.update_state(COMPLETE_CHOICE)

        # Example: "admin:login" is outside dashboard
        resp = client.get(reverse("admin:login"))
        # Must not redirect to wizard
        assert resp.status_code == 200

    def test_static_and_media_are_exempt(self, client, user):
        """Static and media files should bypass wizard check (even if 404)."""
        client.force_login(user)

        for path in ["/static/somefile.js", "/media/upload/test.png"]:
            resp = client.get(path)
            # The middleware must not hijack to wizard
            assert resp.status_code != 302 or resp.url != reverse("dashboard:wizard:customization_wizard")
