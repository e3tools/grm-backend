from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase


class ToggleUserStatusViewTest(DashboardTestCase):
    """Tests for ToggleUserStatusView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True, password="manager_password")
        self.normal_user = UserFactory()
        self.target_user = UserFactory(is_active=True)

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot toggle user status"""
        url = reverse("dashboard:user_management:toggle_status", kwargs={"pk": self.target_user.id})
        resp = self.post(url, {}, user=self.normal_user)
        assert resp.status_code == 403

    def test_deactivate_user_with_correct_password(self):
        """Should deactivate user when correct password provided"""
        # Set password for manager
        self.manager.set_password("TestPass123!")
        self.manager.save()

        url = reverse("dashboard:user_management:toggle_status", kwargs={"pk": self.target_user.id})
        data = {"password": "TestPass123!"}

        resp = self.post(url, data, user=self.manager)
        assert resp.status_code == 302

        self.target_user.refresh_from_db()
        assert self.target_user.is_active is False

    def test_deactivate_user_with_wrong_password(self):
        """Should not deactivate user when wrong password provided"""
        self.manager.set_password("TestPass123!")
        self.manager.save()

        url = reverse("dashboard:user_management:toggle_status", kwargs={"pk": self.target_user.id})
        data = {"password": "WrongPassword"}

        resp = self.post(url, data, user=self.manager)
        assert resp.status_code == 302

        self.target_user.refresh_from_db()
        assert self.target_user.is_active is True  # Unchanged

    def test_activate_user_without_password(self):
        """Should activate user without requiring password"""
        self.target_user.is_active = False
        self.target_user.save()

        url = reverse("dashboard:user_management:toggle_status", kwargs={"pk": self.target_user.id})
        data = {}

        resp = self.post(url, data, user=self.manager)
        assert resp.status_code == 302

        self.target_user.refresh_from_db()
        assert self.target_user.is_active is True

    def test_redirects_to_detail_page(self):
        """Should redirect to user detail page after toggling status"""
        self.target_user.is_active = False
        self.target_user.save()

        url = reverse("dashboard:user_management:toggle_status", kwargs={"pk": self.target_user.id})
        resp = self.post(url, {}, user=self.manager)

        expected_url = reverse("dashboard:user_management:detail", kwargs={"pk": self.target_user.id})
        assert resp.url == expected_url
