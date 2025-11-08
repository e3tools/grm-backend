from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase


class EditUserProfileFormViewTest(DashboardTestCase):
    """Tests for EditUserProfileFormView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.target_user = UserFactory(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone_number="1234567890",
        )

    def test_access_denied_without_ajax(self):
        """View should return 404 without AJAX header"""
        url = reverse("dashboard:user_management:edit_profile", kwargs={"pk": self.target_user.id})
        resp = self.get(url, user=self.manager)
        assert resp.status_code == 404

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot edit user profile"""
        url = reverse("dashboard:user_management:edit_profile", kwargs={"pk": self.target_user.id})
        resp = self.get(url, user=self.normal_user, ajax=True)
        assert resp.status_code == 403

    def test_get_form_with_current_data(self):
        """Should return form with current user data"""
        url = reverse("dashboard:user_management:edit_profile", kwargs={"pk": self.target_user.id})
        resp = self.get(url, user=self.manager, ajax=True)
        assert resp.status_code == 200
        assert "common/modal_form.html" in [t.name for t in resp.templates]

    def test_update_profile_success(self):
        """Should successfully update user profile"""
        url = reverse("dashboard:user_management:edit_profile", kwargs={"pk": self.target_user.id})
        data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane@example.com",
            "phone_number": "0987654321",
        }

        resp = self.post(url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200

        self.target_user.refresh_from_db()
        assert self.target_user.first_name == "Jane"
        assert self.target_user.email == "jane@example.com"

    def test_returns_json_response(self):
        """Should return JSON response after successful update"""
        url = reverse("dashboard:user_management:edit_profile", kwargs={"pk": self.target_user.id})
        data = {
            "first_name": "Updated",
            "last_name": self.target_user.last_name,
            "email": self.target_user.email,
            "phone_number": self.target_user.phone_number,
        }

        resp = self.post(url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        json_data = resp.json()

        # Check keys exist
        assert "msg" in json_data
        assert "user_code" in json_data
        assert "photo" in json_data

        # msg should contain success message
        assert "successfully edited" in json_data["msg"].lower()

        # user_code should be a non-empty string
        assert isinstance(json_data["user_code"], str)
        assert json_data["user_code"] != ""

        # photo should be a URL (default or user photo)
        assert json_data["photo"].startswith("http") or "images/default-avatar.jpg" in json_data["photo"]

    def test_email_change_triggers_info_message(self):
        """Changing email should trigger info message about facilitator code change"""
        url = reverse("dashboard:user_management:edit_profile", kwargs={"pk": self.target_user.id})
        data = {
            "first_name": self.target_user.first_name,
            "last_name": self.target_user.last_name,
            "email": "newemail@example.com",  # different email
            "phone_number": self.target_user.phone_number,
        }

        resp = self.post(url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        json_data = resp.json()
        # msg should contain info about facilitator code change
        assert "facilitator code" in json_data["msg"].lower()
