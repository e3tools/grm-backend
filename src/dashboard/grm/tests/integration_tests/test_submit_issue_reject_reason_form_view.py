from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueFactory,
    IssueStatusFactory,
)
from issues.models import Comment


class SubmitIssueRejectReasonFormViewTest(DashboardTestCase):
    """Integration tests for SubmitIssueRejectReasonFormView."""

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
            status=self.initial_status,
        )
        self.url = reverse("dashboard:grm:submit_issue_reject_reason", kwargs={"issue": self.issue.id})

    def test_post_by_grm_manager_sets_rejected_status_and_reason(self):
        manager = UserFactory(grm_manager=True)
        data = {"reject_reason": "Complaint not valid."}
        resp = self.post(self.url, data=data, ajax=True, user=manager)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.status == self.rejected_status
        assert self.issue.reject_reason == "Complaint not valid."

    def test_post_by_assignee_piu_staff_sets_reject_reason(self):
        GovernmentWorkerFactory(user=self.issue.assignee, administrative_region=self.root_region)

        data = {"reject_reason": "Duplicate complaint."}
        resp = self.post(self.url, data=data, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.status == self.rejected_status
        assert self.issue.reject_reason == "Duplicate complaint."

    def test_post_denied_for_unrelated_user(self):
        outsider = UserFactory()
        data = {"reject_reason": "Unauthorized action."}
        resp = self.post(self.url, data=data, ajax=True, user=outsider)
        assert resp.status_code == 403
        self.issue.refresh_from_db()
        assert self.issue.status == self.initial_status

    def test_post_creates_comment(self):
        """
        When a reject reason is submitted successfully, a Comment should be created
        indicating that the complaint has been rejected.
        """
        manager = UserFactory(grm_manager=True)
        data = {"reject_reason": "Complaint not valid."}
        resp = self.post(self.url, data=data, ajax=True, user=manager)
        assert resp.status_code == 200
        comments = Comment.objects.filter(issue=self.issue, user=manager)
        assert comments.exists()
        assert "rejected" in comments.last().comment.lower()
