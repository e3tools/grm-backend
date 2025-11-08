from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
    IssueFactory,
    IssueStatusFactory,
)


class EditIssueViewTest(DashboardTestCase):
    """
    Integration tests for EditIssueView.
    Ensures that only GRM Managers can edit issues.
    """

    def setUp(self):
        super().setUp()
        self.region = AdministrativeRegionFactory(parent=self.root_region)
        self.department = IssueDepartmentFactory()
        self.dep_level = IssueDepartmentAdministrativeLevelFactory(department=self.department)
        self.category = IssueCategoryFactory(assigned_department=self.dep_level)
        self.status = IssueStatusFactory()
        self.issue = IssueFactory(
            confirmed=True,
            administrative_region=self.region,
        )
        self.url = reverse("dashboard:grm:edit_issue", kwargs={"issue": self.issue.id})

    def test_post_requires_grm_manager(self):
        """GRM manager can POST to edit issue (200)."""
        grm_manager = UserFactory(grm_manager=True)
        # create a valid government worker to assign
        worker = GovernmentWorkerFactory(administrative_region=self.root_region).user
        data = {"assignee": str(worker.id)}
        resp = self.post(self.url, data=data, ajax=True, user=grm_manager)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.assignee == worker

    def test_post_denied_for_non_privileged_user(self):
        """A no PIU staff user gets 403."""
        worker = GovernmentWorkerFactory(administrative_region=self.root_region).user
        resp = self.post(self.url, data={"assignee": str(worker.id)}, ajax=True, user=worker)
        assert resp.status_code == 403

    def test_post_updates_issue_fields(self):
        grm_manager = UserFactory(grm_manager=True)
        new_assignee = GovernmentWorkerFactory(
            administrative_region=self.root_region,
        ).user

        data = {
            "assignee": str(new_assignee.id),
        }
        resp = self.post(self.url, data=data, ajax=True, user=grm_manager)
        assert resp.status_code == 200

        self.issue.refresh_from_db()
        assert self.issue.assignee == new_assignee

    def test_post_invalid_assignee_does_not_change_issue(self):
        grm_manager = UserFactory(grm_manager=True)
        bad_id = 999999
        data = {"assignee": str(bad_id)}
        resp = self.post(self.url, data=data, ajax=True, user=grm_manager)
        assert resp.status_code == 404
        self.issue.refresh_from_db()
        # Should remain unchanged
        assert self.issue.assignee_id != bad_id
