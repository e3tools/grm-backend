import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from dashboard.grm.constants import COMPLETE_CHOICE
from wizard.models import WizardSession

User = get_user_model()


@pytest.mark.django_db
class TestWizardRedirectMiddleware:
    @pytest.fixture
    def grm_manager_user(self):
        return User.objects.create_user(username="manager", password="pass123", grm_manager=True)

    @pytest.fixture
    def normal_user(self):
        return User.objects.create_user(username="normal", password="pass123", grm_manager=False)

    def test_login_url_is_accessible_for_unauthenticated_user(self, client):
        """Login page should never redirect to wizard when unauthenticated."""
        resp = client.get(reverse("dashboard:authentication:login"))
        assert resp.status_code == 200  # middleware lets it pass

    def test_login_url_redirect_to_wizard_for_authenticated_user_if_wizard_incomplete(self, client, grm_manager_user):
        """Login page should redirect to wizard if wizard is missing or incomplete and user is a grm manager."""
        client.force_login(grm_manager_user)
        resp = client.get(reverse("dashboard:authentication:login"))
        # wizard not complete → must redirect to wizard
        assert resp.status_code == 302
        assert resp.url == reverse("dashboard:wizard:customization_wizard")

    def test_wizard_url_is_accessible_for_grm_manager(self, client, grm_manager_user):
        """Customization wizard page should be accessible for grm_manager users regardless of wizard state."""
        client.force_login(grm_manager_user)
        resp = client.get(reverse("dashboard:wizard:customization_wizard"))
        assert resp.status_code == 200  # middleware lets it pass

    def test_wizard_url_redirects_to_admin_for_non_grm_manager(self, client, normal_user):
        """Non-GRM managers should be redirected to admin when trying to access the wizard."""
        client.force_login(normal_user)
        resp = client.get(reverse("dashboard:wizard:customization_wizard"))
        assert resp.status_code == 302
        assert resp.url == reverse("admin:login")

    def test_other_dashboard_url_redirects_if_wizard_incomplete(self, client, grm_manager_user):
        """Other dashboard URLs should redirect to wizard if wizard is missing or incomplete."""
        client.force_login(grm_manager_user)

        # No WizardSession created yet → considered incomplete
        resp = client.get(reverse("dashboard:diagnostics:home"))
        assert resp.status_code == 302
        assert resp.url == reverse("dashboard:wizard:customization_wizard")

    def test_other_dashboard_url_allowed_if_wizard_complete(self, client, grm_manager_user):
        """If wizard is complete, grm_manager should access dashboard URLs normally."""
        client.force_login(grm_manager_user)
        WizardSession.update_state(COMPLETE_CHOICE)

        resp = client.get(reverse("dashboard:diagnostics:home"))
        assert resp.status_code == 200

    def test_other_dashboard_url_accessible_for_non_grm_manager_if_wizard_complete(self, client, normal_user):
        """Non-GRM managers should be able to access other dashboard URLs (not the wizard) if wizard is complete."""
        client.force_login(normal_user)
        WizardSession.update_state(COMPLETE_CHOICE)

        resp = client.get(reverse("dashboard:diagnostics:home"))
        assert resp.status_code == 200

    def test_other_dashboard_url_redirects_to_admin_for_non_grm_manager_if_wizard_incomplete(self, client, normal_user):
        """Non-GRM managers should be redirected to admin for other dashboard URLs if wizard is incomplete."""
        client.force_login(normal_user)
        # No WizardSession created yet → considered incomplete

        resp = client.get(reverse("dashboard:diagnostics:home"))
        assert resp.status_code == 302
        assert resp.url == reverse("admin:login")

    def test_urls_outside_dashboard_are_not_restricted(self, client, grm_manager_user):
        """Middleware should not enforce wizard on non-dashboard apps."""
        client.force_login(grm_manager_user)

        resp = client.get(reverse("admin:login"))
        assert resp.status_code == 200

    def test_urls_outside_dashboard_are_not_restricted_for_normal_user(self, client, normal_user):
        """Non-GRM managers should access non-dashboard URLs normally."""
        client.force_login(normal_user)

        resp = client.get(reverse("admin:login"))
        assert resp.status_code == 200

    def test_static_and_media_are_exempt(self, client, grm_manager_user):
        """Static and media files should bypass wizard check (even if 404)."""
        client.force_login(grm_manager_user)

        for path in ["/static/somefile.js", "/media/upload/test.png"]:
            resp = client.get(path)
            # The middleware must not hijack to wizard
            assert resp.status_code != 302 or resp.url != reverse("dashboard:wizard:customization_wizard")

    def test_static_and_media_are_exempt_for_normal_user(self, client, normal_user):
        """Static and media files should bypass all checks for any user."""
        client.force_login(normal_user)

        for path in ["/static/somefile.js", "/media/upload/test.png"]:
            resp = client.get(path)
            # The middleware must not redirect at all
            assert resp.status_code != 302 or (
                resp.url != reverse("dashboard:wizard:customization_wizard") and resp.url != reverse("admin:login")
            )

    def test_logout_url_is_accessible_for_all_users(self, client, normal_user):
        """Logout URL should be accessible for all authenticated users."""
        client.force_login(normal_user)
        resp = client.get(reverse("dashboard:authentication:logout"))
        # Should not redirect to admin or wizard
        assert resp.status_code != 302 or (
            resp.url != reverse("dashboard:wizard:customization_wizard") and resp.url != reverse("admin:login")
        )
