from unittest.mock import patch

import cryptocode
from django.urls import reverse
from django.utils import timezone

from authentication.factories import GovernmentWorkerFactory, UserFactory
from authentication.models import Cdata
from grm.constants import ALERT_CHOICE, EMAIL_CHOICE
from grm.tests.base import DashboardTestCase
from issues.factories import (
    AdministrativeRegionFactory,
    IssueFactory,
    IssueStatusFactory,
)
from issues.models import Comment, IssueStatusChange


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
        before = timezone.now()
        GovernmentWorkerFactory(user=self.issue.assignee, administrative_region=self.root_region)

        data = {"reject_reason": "Duplicate complaint."}
        resp = self.post(self.url, data=data, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.status == self.rejected_status
        assert self.issue.reject_reason == "Duplicate complaint."

        # Check last_activity was updated
        self.issue.assignee.refresh_from_db()
        assert self.issue.assignee.last_activity >= before

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

    def test_post_closes_previous_isc_and_sets_resolution_for_rejected_status(self):
        """
        Submitting a reject reason that moves the issue to a rejected (terminal) status should:
        - close any previous open IssueStatusChange (set exited_at),
        - set the issue's reject_reason and resolution_date,
        - not create a new IssueStatusChange for the terminal rejected status,
        - create the rejection Comment (covered elsewhere).
        """
        # Ensure there is an open ISC for the current initial_status
        isc_before = (
            IssueStatusChange.objects.filter(issue=self.issue, status=self.initial_status)
            .order_by('-entered_at')
            .first()
        )
        assert isc_before.exited_at is None

        manager = UserFactory(grm_manager=True)
        data = {"reject_reason": "Complaint not valid."}
        resp = self.post(self.url, data=data, ajax=True, user=manager)
        assert resp.status_code == 200

        # Reload issue and verify rejected status and reason
        self.issue.refresh_from_db()
        assert self.issue.status == self.rejected_status
        assert self.issue.reject_reason == "Complaint not valid."

        # Resolution date should be set for terminal/rejected status
        assert self.issue.resolution_date is not None

        # Previous open ISC must have been closed
        isc_before.refresh_from_db()
        assert isc_before.exited_at is not None

        # No new ISC should be created for the terminal rejected_status
        assert not IssueStatusChange.objects.filter(issue=self.issue, status=self.rejected_status).exists()

        # Ensure a comment was created for the rejection
        comments = Comment.objects.filter(issue=self.issue, user=manager)
        assert comments.exists()
        assert "rejected" in comments.last().comment.lower()

    @patch('grm.notifications.send_mail_notification')
    def test_post_sends_notification_with_reject_reason(self, mock_send_mail):
        """
        Submitting reject reason should send notification including the rejection details.
        """

        issue_with_contact = IssueFactory(
            confirmed=True,
            status=self.initial_status,
            administrative_region=self.region,
            contact_medium=ALERT_CHOICE,
            contact_method=EMAIL_CHOICE,
            contact_information="citizen@example.com",
        )

        # Encrypt and save contact information to Cdata
        encrypted_contact = cryptocode.encrypt("citizen@example.com", str(issue_with_contact.id))
        Cdata.objects.create(key=str(issue_with_contact.id), data=encrypted_contact)

        url = reverse("dashboard:grm:submit_issue_reject_reason", kwargs={"issue": issue_with_contact.id})

        data = {"reject_reason": "Issue does not meet criteria for processing."}
        manager = UserFactory(grm_manager=True)
        resp = self.post(url, data=data, ajax=True, user=manager)
        assert resp.status_code == 200

        # Verify notification was sent
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        assert "citizen@example.com" in str(call_args)
        assert "Issue Status Updated" in call_args[1]['subject']
        # Verify reject_reason is in the message
        assert "Reject Reason:" in call_args[1]['message']
        assert "does not meet criteria" in call_args[1]['message']
