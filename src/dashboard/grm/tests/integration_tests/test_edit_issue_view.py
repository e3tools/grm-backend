from unittest.mock import patch

import cryptocode
from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from authentication.models import Cdata
from grm.constants import ALERT_CHOICE, EMAIL_CHOICE
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
        payload = resp.json()
        assert payload["administrative_level"] == new_assignee.governmentworker.administrative_region.administrative_level.name
        assert payload["department"] == new_assignee.governmentworker.department.name

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

    @patch('grm.notifications.send_mail_notification')
    def test_post_sends_notification_when_assigning_with_contact_method(self, mock_send_mail):
        """
        Posting to edit (assign) an issue should send a notification if the issue has a contact_method.
        """
        grm_manager = UserFactory(grm_manager=True)
        new_assignee = GovernmentWorkerFactory(administrative_region=self.root_region).user

        # Create issue with contact information
        issue_with_contact = IssueFactory(
            confirmed=True,
            administrative_region=self.region,
            contact_medium=ALERT_CHOICE,
            contact_method=EMAIL_CHOICE,
            contact_information="citizen@example.com",
        )

        # Encrypt and save contact information to Cdata
        encrypted_contact = cryptocode.encrypt("citizen@example.com", str(issue_with_contact.id))
        Cdata.objects.create(key=str(issue_with_contact.id), data=encrypted_contact)

        url = reverse("dashboard:grm:edit_issue", kwargs={"issue": issue_with_contact.id})
        data = {"assignee": str(new_assignee.id)}

        resp = self.post(url, data=data, ajax=True, user=grm_manager)
        assert resp.status_code == 200

        # Verify notification was sent
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        assert "citizen@example.com" in str(call_args)
        assert "Issue Assigned" in call_args[1]['subject']
