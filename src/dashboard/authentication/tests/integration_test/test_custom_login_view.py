import pytest
from django.test import override_settings
from django.urls import reverse

from authentication.factories import UserFactory
from grm.constants import COMPLETED_CHOICE, NOT_STARTED_CHOICE
from grm.tests.base import DashboardTestCase
from wizard.factories import WizardSectionFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class CustomLoginViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.grm_manager_user = UserFactory(password="pass123", grm_manager=True)
        self.normal_user = UserFactory(password="pass123")
        self.url = reverse("dashboard:authentication:login")

    def test_grm_manager_can_login_even_if_wizard_incomplete(self):
        # wizard not complete
        WizardSectionFactory(status=NOT_STARTED_CHOICE)

        resp = self.post(
            self.url,
            {"username": self.grm_manager_user.email, "password": "pass123"},
            authorized=False,
            follow=True,
        )

        # GRM manager should log in successfully
        assert resp.status_code == 200
        assert resp.context["user"].is_authenticated

    def test_normal_user_blocked_if_wizard_incomplete(self):
        # wizard not complete
        WizardSectionFactory(status=NOT_STARTED_CHOICE)

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
        WizardSectionFactory(status=COMPLETED_CHOICE)

        resp = self.post(
            self.url,
            {"username": self.normal_user.email, "password": "pass123"},
            authorized=False,
            follow=True,
        )

        # User should log in successfully
        assert resp.status_code == 200
        assert resp.context["user"].is_authenticated
