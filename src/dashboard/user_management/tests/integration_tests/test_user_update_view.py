from django.urls import reverse

from authentication.factories import UserFactory
from authentication.models import Facilitator, GovernmentWorker
from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory, IssueDepartmentFactory


class UserUpdateViewTest(DashboardTestCase):
    """Tests for UserUpdateView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.department = IssueDepartmentFactory()

        self.case_manager_user = UserFactory()
        GovernmentWorker.objects.create(
            user=self.case_manager_user,
            department=self.department,
            administrative_region=self.root_region,
        )

    def test_access_granted_for_grm_manager(self):
        """GRM Manager can access update view"""
        url = reverse("dashboard:user_management:update", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        assert resp.status_code == 200
        assert "user_management/update.html" in [t.name for t in resp.templates]

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot access update view"""
        url = reverse("dashboard:user_management:update", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.normal_user)
        assert resp.status_code == 403

    def test_update_user_basic_info(self):
        """Should successfully update user basic information"""
        url = reverse("dashboard:user_management:update", kwargs={"pk": self.case_manager_user.id})
        data = {
            "first_name": "UpdatedFirst",
            "last_name": "UpdatedLast",
            "email": self.case_manager_user.email,
            "phone_number": "9999999999",
            "administrative_region": self.root_region.id,
            "department": self.department.id,
            "is_department_head": False,
        }

        resp = self.post(url, data, user=self.manager)
        assert resp.status_code == 302

        self.case_manager_user.refresh_from_db()
        assert self.case_manager_user.first_name == "UpdatedFirst"
        assert self.case_manager_user.phone_number == "9999999999"

    def test_update_case_manager_department(self):
        """Should successfully update Case Manager department"""
        new_department = IssueDepartmentFactory()
        url = reverse("dashboard:user_management:update", kwargs={"pk": self.case_manager_user.id})
        data = {
            "first_name": self.case_manager_user.first_name,
            "last_name": self.case_manager_user.last_name,
            "email": self.case_manager_user.email,
            "phone_number": self.case_manager_user.phone_number,
            "administrative_region": self.root_region.id,
            "department": new_department.id,
            "is_department_head": False,
        }

        resp = self.post(url, data, user=self.manager)
        assert resp.status_code == 302

        worker = GovernmentWorker.objects.get(user=self.case_manager_user)
        assert worker.department == new_department

    def test_assign_as_department_head(self):
        """Should successfully assign user as department head"""
        url = reverse("dashboard:user_management:update", kwargs={"pk": self.case_manager_user.id})
        data = {
            "first_name": self.case_manager_user.first_name,
            "last_name": self.case_manager_user.last_name,
            "email": self.case_manager_user.email,
            "phone_number": self.case_manager_user.phone_number,
            "administrative_region": self.root_region.id,
            "department": self.department.id,
            "is_department_head": True,
        }

        resp = self.post(url, data, user=self.manager)
        assert resp.status_code == 302

        self.department.refresh_from_db()
        assert self.department.head == self.case_manager_user

    def test_cannot_assign_as_head_if_department_has_head(self):
        """Should fail when trying to assign as head if department already has one"""
        existing_head = UserFactory()
        self.department.head = existing_head
        self.department.save()

        url = reverse("dashboard:user_management:update", kwargs={"pk": self.case_manager_user.id})
        data = {
            "first_name": self.case_manager_user.first_name,
            "last_name": self.case_manager_user.last_name,
            "email": self.case_manager_user.email,
            "phone_number": self.case_manager_user.phone_number,
            "administrative_region": self.root_region.id,
            "department": self.department.id,
            "is_department_head": True,
        }

        resp = self.post(url, data, user=self.manager)
        assert resp.status_code == 200  # Form validation fails, stays on page

        self.department.refresh_from_db()
        assert self.department.head == existing_head  # Unchanged

    def test_update_facilitator_region(self):
        """Should successfully update Facilitator administrative region"""
        facilitator_user = UserFactory()
        child_region = AdministrativeRegionFactory(parent=self.root_region)
        Facilitator.objects.create(
            user=facilitator_user,
            administrative_region=self.root_region,
            village_secretary=False,
        )

        url = reverse("dashboard:user_management:update", kwargs={"pk": facilitator_user.id})
        data = {
            "first_name": facilitator_user.first_name,
            "last_name": facilitator_user.last_name,
            "email": facilitator_user.email,
            "phone_number": facilitator_user.phone_number,
            "administrative_region": child_region.id,
            "village_secretary": True,
        }

        resp = self.post(url, data, user=self.manager)
        assert resp.status_code == 302

        facilitator = Facilitator.objects.get(user=facilitator_user)
        assert facilitator.administrative_region == child_region
        assert facilitator.village_secretary is True

    def test_update_facilitator_email(self):
        """Username changes to the value of the email"""
        facilitator_user = UserFactory()
        Facilitator.objects.create(user=facilitator_user, administrative_region=self.root_region)

        url = reverse("dashboard:user_management:update", kwargs={"pk": facilitator_user.id})
        data = {
            "first_name": facilitator_user.first_name,
            "last_name": facilitator_user.last_name,
            "email": "newemail@example.com",  # different email
            "phone_number": facilitator_user.phone_number,
            "administrative_region": self.root_region.id,
            "village_secretary": True,
        }

        resp = self.post(url, data, user=self.manager)
        assert resp.status_code == 302
        facilitator_user.refresh_from_db()
        assert facilitator_user.username == data["email"]

    def test_success_url_redirects_to_detail(self):
        """Should redirect to user detail page after successful update"""
        url = reverse("dashboard:user_management:update", kwargs={"pk": self.case_manager_user.id})
        data = {
            "first_name": "Updated",
            "last_name": self.case_manager_user.last_name,
            "email": self.case_manager_user.email,
            "phone_number": self.case_manager_user.phone_number,
            "administrative_region": self.root_region.id,
            "department": self.department.id,
            "is_department_head": False,
        }

        resp = self.post(url, data, user=self.manager)
        expected_url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        assert resp.url == expected_url
