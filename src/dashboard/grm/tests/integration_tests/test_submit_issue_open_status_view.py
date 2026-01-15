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
from issues.models import IssueStatusChange


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
        before = timezone.now()
        manager = UserFactory(grm_manager=True)
        resp = self.post(self.url, data={}, ajax=True, user=manager)
        assert resp.status_code == 200

        # Check last_activity was updated
        manager.refresh_from_db()
        assert manager.last_activity >= before

        # Reload and assert status changed
        self.issue.refresh_from_db()
        assert self.issue.status == self.open_status

        # Verify IssueStatusChange behavior:
        # - any previous open ISC for the initial status should be closed
        prev_open = (
            IssueStatusChange.objects.filter(issue=self.issue, status=self.initial_status)
            .order_by('-entered_at')
            .first()
        )
        assert prev_open.exited_at is not None

        # - a new open ISC for the open_status should exist
        new_isc = (
            IssueStatusChange.objects.filter(issue=self.issue, status=self.open_status).order_by('-entered_at').first()
        )
        assert new_isc is not None
        assert new_isc.exited_at is None

    def test_post_by_assignee_piu_staff_sets_open_status(self):
        GovernmentWorkerFactory(user=self.issue.assignee, administrative_region=self.root_region)
        resp = self.post(self.url, data={}, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 200

        # Reload and assert status changed
        self.issue.refresh_from_db()
        assert self.issue.status == self.open_status

        # Verify IssueStatusChange behavior:
        prev_open = (
            IssueStatusChange.objects.filter(issue=self.issue, status=self.initial_status)
            .order_by('-entered_at')
            .first()
        )
        assert prev_open.exited_at is not None

        new_isc = (
            IssueStatusChange.objects.filter(issue=self.issue, status=self.open_status).order_by('-entered_at').first()
        )
        assert new_isc is not None
        assert new_isc.exited_at is None

    def test_post_denied_for_unrelated_user(self):
        outsider = UserFactory()
        resp = self.post(self.url, data={}, ajax=True, user=outsider)
        assert resp.status_code == 403
        self.issue.refresh_from_db()
        assert self.issue.status == self.initial_status

        # Ensure no ISC was created for open_status and any existing ISC remains unchanged
        assert not IssueStatusChange.objects.filter(issue=self.issue, status=self.open_status).exists()

    @patch('grm.notifications.send_mail_notification')
    def test_post_sends_notification_when_changing_to_open_status(self, mock_send_mail):
        """
        Posting to change status to open should send a notification if the issue has a contact_method.
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

        url = reverse("dashboard:grm:submit_issue_open_status", kwargs={"issue": issue_with_contact.id})
        manager = UserFactory(grm_manager=True)
        resp = self.post(url, data={}, ajax=True, user=manager)
        assert resp.status_code == 200

        # Verify notification was sent
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        assert "citizen@example.com" in str(call_args)
        assert "Issue Status Updated" in call_args[1]['subject']
