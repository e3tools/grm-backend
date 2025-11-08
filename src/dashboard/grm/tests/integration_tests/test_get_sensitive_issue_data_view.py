from django.urls import reverse

from authentication.factories import UserFactory
from authentication.models import GovernmentWorker
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
    IssueFactory,
)


class GetSensitiveIssueDataViewTest(DashboardTestCase):
    """
    Integration tests for GetSensitiveIssueDataView.

    Cases covered:
    - Case Manager who is assignee + correct password -> returns sensitive data payload.
    - Case Manager who is assignee + wrong password -> returns message and no sensitive data.
    - GRM Manager (not a GovernmentWorker) -> access denied (403).
    - Case Manager who is NOT the assignee -> access denied (403).
    """

    def setUp(self):
        super().setUp()
        # create a region under root_region to satisfy region constraints in fixtures
        self.region = AdministrativeRegionFactory(parent=self.root_region)

        # create a department/category for completeness (not strictly required)
        self.department = IssueDepartmentFactory()
        self.dep_level = IssueDepartmentAdministrativeLevelFactory(department=self.department)
        self.category = IssueCategoryFactory(assigned_department=self.dep_level)

        # create an issue; we'll change assignee per test scenario
        self.issue = IssueFactory(confirmed=True, administrative_region=self.region, category=self.category)

        # url expects issue id in the route (matches your routing in views)
        self.url = reverse("dashboard:grm:get_sensitive_issue_data")

    def _make_case_manager(self, *, region=None, set_password="secret"):
        """Helper to create a GovernmentWorker user with a known password."""
        user = UserFactory()
        user.set_password(set_password)
        user.save()
        dept = IssueDepartmentFactory()
        GovernmentWorker.objects.create(user=user, department=dept, administrative_region=region or self.region)
        return user

    def test_case_manager_assignee_with_correct_password_gets_data(self):
        # Make a government worker who will be the assignee
        worker_user = self._make_case_manager(set_password="pwd123")
        # assign the issue to that user
        self.issue.assignee = worker_user
        self.issue.save()

        # Post with correct password
        resp = self.post(self.url, data={"password": "pwd123", "id": self.issue.id}, ajax=True, user=worker_user)
        assert resp.status_code == 200

        data = resp.json()
        # The view always returns at least the 'data' key (may be None or dict)
        assert "data" in data
        # If no Pdata/Cdata exist, data["data"] should be a dict with keys 'citizen' and 'contact' (may be None)
        assert isinstance(data["data"], dict)
        assert set(data["data"].keys()) == {"citizen", "contact"}

    def test_case_manager_assignee_with_wrong_password_gets_message_and_no_sensitive_data(self):
        worker_user = self._make_case_manager(set_password="pwd123")
        self.issue.assignee = worker_user
        self.issue.save()

        resp = self.post(self.url, data={"password": "wrong"}, ajax=True, user=worker_user)
        # view returns 200 but includes an error message in JSON (it adds a Django message and sets context['msg'])
        assert resp.status_code == 200

        data = resp.json()
        # data key exists but should be None (not populated)
        assert "data" in data
        assert data["data"] is None
        # and there should be a 'msg' key produced by the view
        assert "msg" in data

    def test_non_government_user_cannot_access_view(self):
        # A GRM manager (not a governmentworker) should be denied
        manager = UserFactory(grm_manager=True)
        resp = self.post(self.url, data={"password": "irrelevant"}, ajax=True, user=manager)
        # PermissionDenied -> view should produce HTTP 403
        assert resp.status_code == 403

    def test_government_worker_not_assignee_is_forbidden(self):
        # Create a worker who is NOT the assignee of the issue
        worker_user = self._make_case_manager(set_password="pwd123")
        # Ensure the issue is assigned to someone else
        other_user = UserFactory()
        self.issue.assignee = other_user
        self.issue.save()

        resp = self.post(self.url, data={"password": "pwd123"}, ajax=True, user=worker_user)
        # Not assignee -> should raise PermissionDenied -> 403
        assert resp.status_code == 403
