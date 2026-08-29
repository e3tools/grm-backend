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


class UserListViewTest(DashboardTestCase):
    """Tests for UserListView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.department = IssueDepartmentFactory()

        # Create different types of users
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
            village_secretary=False,
        )

        self.url = reverse("dashboard:user_management:list")

    def test_access_denied_without_ajax(self):
        """View should return 404 without AJAX header"""
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 404

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot access even with AJAX"""
        resp = self.get(self.url, user=self.normal_user, ajax=True)
        assert resp.status_code == 403

    def test_list_grm_managers(self):
        """Should list only GRM Managers when user_type is grm_manager"""
        resp = self.get(
            f"{self.url}?user_type={GRM_MANAGER_CHOICE}",
            user=self.manager,
            ajax=True,
        )
        assert resp.status_code == 200
        ctx = self.get_context(resp)
        user_ids = [u['user'].id for u in ctx['users_with_type']]
        assert self.grm_manager_user.id in user_ids
        assert self.case_manager_user.id not in user_ids
        assert self.facilitator_user.id not in user_ids

    def test_list_case_managers(self):
        """Should list only Case Managers when user_type is case_manager"""
        resp = self.get(
            f"{self.url}?user_type={CASE_MANAGER_CHOICE}",
            user=self.manager,
            ajax=True,
        )
        assert resp.status_code == 200
        ctx = self.get_context(resp)
        user_ids = [u['user'].id for u in ctx['users_with_type']]
        assert self.case_manager_user.id in user_ids
        assert self.grm_manager_user.id not in user_ids
        assert self.facilitator_user.id not in user_ids

    def test_list_facilitators(self):
        """Should list only Facilitators when user_type is facilitator"""
        resp = self.get(
            f"{self.url}?user_type={FACILITATOR_CHOICE}",
            user=self.manager,
            ajax=True,
        )
        assert resp.status_code == 200
        ctx = self.get_context(resp)
        user_ids = [u['user'].id for u in ctx['users_with_type']]
        assert self.facilitator_user.id in user_ids
        assert self.grm_manager_user.id not in user_ids
        assert self.case_manager_user.id not in user_ids

    def test_role_info_for_case_manager_head(self):
        """Should show department head indicator for department heads"""
        self.department.head = self.case_manager_user
        self.department.save()

        resp = self.get(
            f"{self.url}?user_type={CASE_MANAGER_CHOICE}",
            user=self.manager,
            ajax=True,
        )
        ctx = self.get_context(resp)
        case_manager_info = next(u for u in ctx['users_with_type'] if u['user'].id == self.case_manager_user.id)
        assert "(Head)" in case_manager_info['role_info'] or "Head" in case_manager_info['role_info']

    def test_role_info_for_village_secretary(self):
        """Should show village secretary indicator for facilitators"""
        facilitator = Facilitator.objects.get(user=self.facilitator_user)
        facilitator.village_secretary = True
        facilitator.save()

        resp = self.get(
            f"{self.url}?user_type={FACILITATOR_CHOICE}",
            user=self.manager,
            ajax=True,
        )
        ctx = self.get_context(resp)
        facilitator_info = next(u for u in ctx['users_with_type'] if u['user'].id == self.facilitator_user.id)
        assert (
            "(Village Secretary)" in facilitator_info['role_info']
            or "Village Secretary" in facilitator_info['role_info']
        )
