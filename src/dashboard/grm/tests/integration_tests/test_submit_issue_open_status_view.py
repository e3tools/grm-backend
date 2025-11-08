from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueFactory,
    IssueStatusFactory,
)


class SubmitIssueOpenStatusViewTest(DashboardTestCase):
    """Integration tests for SubmitIssueOpenStatusView."""

    def setUp(self):
        super().setUp()
        self.region = AdministrativeRegionFactory(parent=self.root_region)

        # Correct setup: four statuses with exclusive flags
        self.initial_status = IssueStatusFactory(initial_status=True)
        self.open_status = IssueStatusFactory(open_status=True)
        self.final_status = IssueStatusFactory(final_status=True)
        self.rejected_status = IssueStatusFactory(rejected_status=True)

        self.issue = IssueFactory(
            confirmed=True,
            administrative_region=self.region,
            status=self.initial_status,
        )
        self.url = reverse("dashboard:grm:submit_issue_open_status", kwargs={"issue": self.issue.id})

    def test_post_by_grm_manager_sets_open_status(self):
        manager = UserFactory(grm_manager=True)
        resp = self.post(self.url, data={}, ajax=True, user=manager)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.status == self.open_status

    def test_post_by_assignee_piu_staff_sets_open_status(self):
        GovernmentWorkerFactory(user=self.issue.assignee, administrative_region=self.root_region)
        resp = self.post(self.url, data={}, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.status == self.open_status

    def test_post_denied_for_unrelated_user(self):
        outsider = UserFactory()
        resp = self.post(self.url, data={}, ajax=True, user=outsider)
        assert resp.status_code == 403
        self.issue.refresh_from_db()
        assert self.issue.status == self.initial_status
