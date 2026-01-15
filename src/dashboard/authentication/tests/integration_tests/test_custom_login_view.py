import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from authentication.factories import FacilitatorFactory, UserFactory
from grm.tests.base import DashboardTestCase
from wizard.constants import COMPLETED_CHOICE, NOT_STARTED_CHOICE
from wizard.models import WizardSection


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class CustomLoginViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.grm_owner_user = UserFactory(password="pass123", grm_manager=True)
        self.normal_user = UserFactory(password="pass123")
        self.url = reverse("dashboard:authentication:login")

    def test_grm_owner_can_login_even_if_wizard_incomplete(self):
        before = timezone.now()
        resp = self.post(
            self.url,
            {"username": self.grm_owner_user.email, "password": "pass123"},
            authorized=False,
            follow=True,
        )

        # GRM manager should log in successfully
        assert resp.status_code == 200
        assert resp.context["user"].is_authenticated

        # Check last_activity was updated
        self.grm_owner_user.refresh_from_db()
        assert self.grm_owner_user.last_activity >= before

    def test_normal_user_blocked_if_wizard_incomplete(self):
        # wizard not complete
        WizardSection.objects.update(status=NOT_STARTED_CHOICE)

        resp = self.post(
            self.url,
            {"username": self.normal_user.email, "password": "pass123"},
            authorized=False,
            follow=True,
        )

        # User should not be authenticated
        assert resp.status_code == 200
        assert not resp.context["user"].is_authenticated
        assert "Login is not allowed until the customization wizard is completed." in resp.content.decode()

    def test_normal_user_can_login_if_wizard_complete(self):
        # wizard complete
        WizardSection.objects.update(status=COMPLETED_CHOICE)

        resp = self.post(
            self.url,
            {"username": self.normal_user.email, "password": "pass123"},
            authorized=False,
            follow=True,
        )

        # User should log in successfully
        assert resp.status_code == 200
        assert resp.context["user"].is_authenticated

    def test_facilitator_user_is_blocked(self):
        # wizard complete to isolate facilitator rule
        WizardSection.objects.update(status=COMPLETED_CHOICE)

        facilitator = FacilitatorFactory(administrative_region=self.root_region)
        user = facilitator.user
        user.set_password("pass123")
        user.save()

        resp = self.post(
            self.url,
            {"username": user.email, "password": "pass123"},
            authorized=False,
            follow=True,
        )

        assert resp.status_code == 200
        assert not resp.context["user"].is_authenticated
        assert (
            "Your user account is not authorized to access this system. Please use the mobile application instead."
            in resp.content.decode()
        )
