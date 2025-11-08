import pytest
from django.test import TestCase
from django.urls import reverse

from authentication.factories import UserFactory
from wizard.constants import COMPLETED_CHOICE
from wizard.models import WizardSection


@pytest.mark.django_db
class TestWizardRedirectMiddleware(TestCase):

    def setUp(self):
        self.grm_owner_user = UserFactory(grm_owner=True)
        self.normal_user = UserFactory()
        self.customization_url = reverse("wizard:customization_wizard")
        self.login_url = reverse("dashboard:authentication:login")
        self.logout_url = reverse("dashboard:authentication:logout")
        self.dashboard = reverse("dashboard:diagnostics:home")

    def test_login_url_is_accessible_for_unauthenticated_user(self):
        """Login page should always be accessible when unauthenticated."""
        resp = self.client.get(self.login_url)
        assert resp.status_code == 200  # middleware lets it pass

    def test_login_url_redirect_to_wizard_for_authenticated_user_if_wizard_incomplete(self):
        """Login page should redirect to wizard if wizard is missing or incomplete and user is a grm manager."""
        self.client.force_login(self.grm_owner_user)
        resp = self.client.get(self.login_url)
        # wizard not complete → must redirect to wizard
        assert resp.status_code == 302
        assert resp.url == self.customization_url

    def test_wizard_url_is_accessible_for_grm_owner(self):
        """Customization wizard page should be accessible for grm_owner users regardless of wizard state."""
        self.client.force_login(self.grm_owner_user)
        resp = self.client.get(self.customization_url)
        assert resp.status_code == 200  # middleware lets it pass

    def test_wizard_url_raises_404_for_non_grm_owner(self):
        """Non-GRM manager should get 404 when accessing wizard URL."""
        self.client.force_login(self.normal_user)
        resp = self.client.get(self.customization_url)
        assert resp.status_code == 404

    def test_wizard_url_raises_404_for_all_users_if_wizard_complete(self):
        """All types of users get 404 if wizard is complete."""
        WizardSection.objects.update(status=COMPLETED_CHOICE)
        self.client.force_login(self.normal_user)
        resp = self.client.get(self.customization_url)
        assert resp.status_code == 404

        self.client.force_login(self.grm_owner_user)
        resp = self.client.get(self.customization_url)
        assert resp.status_code == 404

    def test_other_dashboard_url_redirects_if_wizard_incomplete(self):
        """Other dashboard URLs should redirect to wizard if wizard is missing or incomplete."""
        self.client.force_login(self.grm_owner_user)

        # No WizardSession created yet → considered incomplete
        resp = self.client.get(self.dashboard)
        assert resp.status_code == 302
        assert resp.url == self.customization_url

    def test_other_dashboard_url_allowed_if_wizard_complete(self):
        """Dashboard URLs accessible if wizard is complete and user is grm_owner."""
        self.client.force_login(self.grm_owner_user)
        WizardSection.objects.update(status=COMPLETED_CHOICE)

        resp = self.client.get(self.dashboard)
        assert resp.status_code == 200

    def test_other_dashboard_url_accessible_for_non_grm_owner_if_wizard_complete(self):
        """Non-GRM managers should be able to access other dashboard URLs (not the wizard) if wizard is complete."""
        self.client.force_login(self.normal_user)
        WizardSection.objects.update(status=COMPLETED_CHOICE)

        resp = self.client.get(self.dashboard)
        assert resp.status_code == 200

    def test_other_dashboard_url_raises_404_for_non_grm_owner_if_wizard_incomplete(self):
        """Non-GRM managers get 404 if wizard is incomplete."""
        self.client.force_login(self.normal_user)
        resp = self.client.get(self.dashboard)
        assert resp.status_code == 404

    def test_urls_outside_dashboard_are_not_restricted(self):
        """Middleware should not enforce wizard on non-dashboard apps."""
        self.client.force_login(self.grm_owner_user)

        resp = self.client.get(reverse("admin:login"))
        assert resp.status_code == 200

    def test_urls_outside_dashboard_are_not_restricted_for_normal_user(self):
        """Non-GRM managers should access non-dashboard URLs normally."""
        self.client.force_login(self.normal_user)

        resp = self.client.get(reverse("admin:login"))
        assert resp.status_code == 200

    def test_static_and_media_are_exempt(self):
        """Static and media files should bypass wizard check (even if 404)."""
        self.client.force_login(self.grm_owner_user)

        for path in ["/static/somefile.js", "/media/upload/test.png"]:
            resp = self.client.get(path)
            assert resp.status_code != 302

    def test_static_and_media_are_exempt_for_normal_user(self):
        """Static and media files should bypass all checks for any user."""
        self.client.force_login(self.normal_user)

        for path in ["/static/somefile.js", "/media/upload/test.png"]:
            resp = self.client.get(path)
            assert resp.status_code != 302

    def test_logout_url_is_accessible_for_all_users(self):
        """Logout URL is always accessible."""
        self.client.force_login(self.normal_user)
        resp = self.client.get(reverse("dashboard:authentication:logout"))
        assert resp.status_code == 302
        assert resp.url == self.login_url
