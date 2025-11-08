from django.urls import reverse

from authentication.factories import UserFactory
from dashboard.user_management.constants import (
    CASE_MANAGER_CHOICE,
    FACILITATOR_CHOICE,
    GRM_MANAGER_CHOICE,
)
from grm.tests.base import DashboardTestCase
from issues.factories import IssueDepartmentFactory


class CreateUserViewTest(DashboardTestCase):
    """Tests for CreateUserView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.department = IssueDepartmentFactory()
        self.url = reverse("dashboard:user_management:create")

    def test_access_denied_without_ajax(self):
        """View should return 404 without AJAX header"""
        resp = self.post(self.url, {}, user=self.manager)
        assert resp.status_code == 404

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot create users"""
        resp = self.post(self.url, {}, user=self.normal_user, ajax=True)
        assert resp.status_code == 403

    def test_create_grm_manager_success(self):
        """Should successfully create a GRM Manager"""
        data = {
            "user_type": GRM_MANAGER_CHOICE,
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "email": "john@example.com",
            "phone_number": "1234567890",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        }

        resp = self.post(self.url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        json_data = resp.json()
        assert json_data["success"] is True
        assert "user_id" in json_data

        from authentication.models import User

        user = User.objects.get(id=json_data["user_id"])
        assert user.grm_manager is True
        assert user.first_name == "John"

    def test_create_case_manager_success(self):
        """Should successfully create a Case Manager"""
        data = {
            "user_type": CASE_MANAGER_CHOICE,
            "first_name": "Jane",
            "last_name": "Smith",
            "username": "janesmith",
            "email": "jane@example.com",
            "phone_number": "0987654321",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "department": self.department.id,
            "case_manager_administrative_region": self.root_region.id,
            "is_department_head": False,
        }

        resp = self.post(self.url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        json_data = resp.json()
        assert json_data["success"] is True

        from authentication.models import User

        user = User.objects.get(id=json_data["user_id"])
        assert hasattr(user, "governmentworker")
        assert user.governmentworker.department == self.department

    def test_create_facilitator_success(self):
        """Should successfully create a Facilitator"""
        data = {
            "user_type": FACILITATOR_CHOICE,
            "first_name": "Bob",
            "last_name": "Brown",
            "username": "bobbrown",
            "email": "bob@example.com",
            "phone_number": "5555555555",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
            "administrative_region": self.root_region.id,
            "village_secretary": True,
        }

        resp = self.post(self.url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        json_data = resp.json()
        assert json_data["success"] is True

        from authentication.models import User

        user = User.objects.get(id=json_data["user_id"])
        assert hasattr(user, "facilitator")
        assert user.facilitator.village_secretary is True

    def test_create_user_with_mismatched_passwords(self):
        """Should fail when passwords don't match"""
        data = {
            "user_type": GRM_MANAGER_CHOICE,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
            "email": "test@example.com",
            "phone_number": "1111111111",
            "password": "SecurePass123!",
            "confirm_password": "DifferentPass123!",
        }

        resp = self.post(self.url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        json_data = resp.json()
        assert json_data["success"] is False
        assert "errors" in json_data
        assert "confirm_password" in json_data["errors"]

    def test_create_user_with_duplicate_email(self):
        """Should fail when email already exists"""
        UserFactory(email="duplicate@example.com")

        data = {
            "user_type": GRM_MANAGER_CHOICE,
            "first_name": "Test",
            "last_name": "User",
            "username": "newuser",
            "email": "duplicate@example.com",
            "phone_number": "1111111111",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        }

        resp = self.post(self.url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        json_data = resp.json()
        assert json_data["success"] is False
        assert "errors" in json_data

    def test_create_user_with_invalid_user_type(self):
        """Should fail with invalid user type"""
        data = {
            "user_type": "invalid_type",
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
            "email": "test@example.com",
            "phone_number": "1111111111",
            "password": "SecurePass123!",
            "confirm_password": "SecurePass123!",
        }

        resp = self.post(self.url, data, user=self.manager, ajax=True)
        assert resp.status_code == 200
        json_data = resp.json()
        assert json_data["success"] is False
        assert "errors" in json_data
