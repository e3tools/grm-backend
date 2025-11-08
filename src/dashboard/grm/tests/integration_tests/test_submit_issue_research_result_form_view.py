from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueFactory,
    IssueStatusFactory,
)
from issues.models import Comment


class SubmitIssueResearchResultFormViewTest(DashboardTestCase):
    """Integration tests for SubmitIssueResearchResultFormView."""

    def setUp(self):
        super().setUp()
        self.region = AdministrativeRegionFactory(parent=self.root_region)

        # status flags
        self.initial_status = IssueStatusFactory(initial_status=True)
        self.open_status = IssueStatusFactory(open_status=True)
        self.final_status = IssueStatusFactory(final_status=True)
        self.rejected_status = IssueStatusFactory(rejected_status=True)

        self.issue = IssueFactory(
            confirmed=True,
            administrative_region=self.region,
            status=self.open_status,
        )
        self.url = reverse("dashboard:grm:submit_issue_research_result", kwargs={"issue": self.issue.id})

    def test_post_by_grm_manager_sets_final_status_and_result(self):
        manager = UserFactory(grm_manager=True)
        data = {"research_result": "After review, issue resolved."}
        resp = self.post(self.url, data=data, ajax=True, user=manager)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.status == self.final_status
        assert self.issue.research_result == "After review, issue resolved."

    def test_post_by_assignee_piu_staff_sets_result(self):
        GovernmentWorkerFactory(user=self.issue.assignee, administrative_region=self.root_region)
        data = {"research_result": "Confirmed and addressed."}
        resp = self.post(self.url, data=data, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.status == self.final_status
        assert self.issue.research_result == "Confirmed and addressed."

    def test_post_denied_for_unrelated_user(self):
        outsider = UserFactory()
        data = {"research_result": "Attempt by outsider"}
        resp = self.post(self.url, data=data, ajax=True, user=outsider)
        assert resp.status_code == 403
        self.issue.refresh_from_db()
        assert self.issue.status == self.open_status

    def test_post_creates_comment(self):
        """
        When a research result is submitted successfully, a Comment should be created
        indicating that the complaint has been resolved.
        """
        manager = UserFactory(grm_manager=True)
        data = {"research_result": "Resolution text"}
        resp = self.post(self.url, data=data, ajax=True, user=manager)
        assert resp.status_code == 200
        comments = Comment.objects.filter(issue=self.issue, user=manager)
        assert comments.exists()
        assert "resolved" in comments.last().comment.lower()
