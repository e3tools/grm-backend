from django.urls import reverse

from authentication.factories import UserFactory
from authentication.models import Facilitator, GovernmentWorker
from dashboard.user_management.constants import (
    CASE_MANAGER_CHOICE,
    FACILITATOR_CHOICE,
    GRM_MANAGER_CHOICE,
)
from grm.tests.base import DashboardTestCase
from issues.factories import IssueDepartmentFactory


class UserDetailViewTest(DashboardTestCase):
    """Tests for UserDetailView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.department = IssueDepartmentFactory()

        self.grm_manager_user = UserFactory(grm_manager=True)

        self.case_manager_user = UserFactory()
        GovernmentWorker.objects.create(
            user=self.case_manager_user,
            department=self.department,
            administrative_region=self.root_region,
        )

        self.facilitator_user = UserFactory()
        Facilitator.objects.create(
            user=self.facilitator_user,
            administrative_region=self.root_region,
            village_secretary=True,
        )

    def test_access_granted_for_grm_manager(self):
        """GRM Manager can view user details"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.grm_manager_user.id})
        resp = self.get(url, user=self.manager)
        assert resp.status_code == 200
        assert "user_management/profile.html" in [t.name for t in resp.templates]

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot view user details"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.grm_manager_user.id})
        resp = self.get(url, user=self.normal_user)
        assert resp.status_code == 403

    def test_grm_manager_role_info(self):
        """Should display correct role info for GRM Manager"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.grm_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["user_type"] == GRM_MANAGER_CHOICE
        assert "GRM Manager" in ctx["role_info"]["type_display"]

    def test_case_manager_role_info(self):
        """Should display correct role info for Case Manager"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["user_type"] == CASE_MANAGER_CHOICE
        assert ctx["role_info"]["department"] == self.department.name

    def test_case_manager_department_head_indicator(self):
        """Should indicate if Case Manager is department head"""
        self.department.head = self.case_manager_user
        self.department.save()

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["role_info"]["is_department_head"] is True

    def test_facilitator_role_info(self):
        """Should display correct role info for Facilitator"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.facilitator_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["user_type"] == FACILITATOR_CHOICE
        assert ctx["role_info"]["village_secretary"] is True

    def test_password_confirm_form_present(self):
        """Password confirm form should be in context"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.grm_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert "password_confirm_form" in ctx
