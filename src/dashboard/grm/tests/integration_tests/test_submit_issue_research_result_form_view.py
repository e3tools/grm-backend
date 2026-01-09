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
        before = timezone.now()
        manager = UserFactory(grm_manager=True)
        data = {"research_result": "After review, issue resolved."}
        resp = self.post(self.url, data=data, ajax=True, user=manager)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.status == self.final_status
        assert self.issue.research_result == "After review, issue resolved."

        # Check last_activity was updated
        manager.refresh_from_db()
        assert manager.last_activity >= before

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

    def test_post_closes_previous_isc_and_sets_resolution_when_final_status(self):
        """
        Submitting a research result that moves the issue to a final status should:
        - close any previous open IssueStatusChange (set exited_at),
        - set the issue's resolution_date,
        - NOT create a new IssueStatusChange for the terminal status,
        - still create the resolution Comment (covered elsewhere).
        """
        # Ensure there is an open ISC for the current open_status
        isc_before = (
            IssueStatusChange.objects.filter(issue=self.issue, status=self.open_status).order_by('-entered_at').first()
        )
        assert isc_before.exited_at is None

        manager = UserFactory(grm_manager=True)
        data = {"research_result": "Final resolution applied."}
        resp = self.post(self.url, data=data, ajax=True, user=manager)
        assert resp.status_code == 200

        # Reload issue and verify final status and research_result
        self.issue.refresh_from_db()
        assert self.issue.status == self.final_status
        assert self.issue.research_result == "Final resolution applied."

        # Resolution date must be set for terminal status
        assert self.issue.resolution_date is not None

        # Previous open ISC must have been closed
        isc_before.refresh_from_db()
        assert isc_before.exited_at is not None

        # No new ISC should be created for the terminal final_status
        assert not IssueStatusChange.objects.filter(issue=self.issue, status=self.final_status).exists()

        # Comment creation is already tested elsewhere, but ensure at least one comment exists for completeness
        comments = Comment.objects.filter(issue=self.issue, user=manager)
        assert comments.exists()

    @patch('grm.notifications.send_mail_notification')
    def test_post_sends_notification_with_research_result(self, mock_send_mail):
        """
        Submitting research result should send notification including the resolution details.
        """
        issue_with_contact = IssueFactory(
            confirmed=True,
            status=self.open_status,
            administrative_region=self.region,
            contact_medium=ALERT_CHOICE,
            contact_method=EMAIL_CHOICE,
            contact_information="citizen@example.com",
        )

        # Encrypt and save contact information to Cdata
        encrypted_contact = cryptocode.encrypt("citizen@example.com", str(issue_with_contact.id))
        Cdata.objects.create(key=str(issue_with_contact.id), data=encrypted_contact)

        url = reverse("dashboard:grm:submit_issue_research_result", kwargs={"issue": issue_with_contact.id})

        data = {"research_result": "The issue has been resolved successfully."}
        manager = UserFactory(grm_manager=True)
        resp = self.post(url, data=data, ajax=True, user=manager)
        assert resp.status_code == 200

        # Verify notification was sent
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        assert "citizen@example.com" in str(call_args)
        assert "Issue Status Updated" in call_args[1]['subject']
        # Verify research_result is in the message
        assert "Resolution:" in call_args[1]['message']
        assert "resolved successfully" in call_args[1]['message']
