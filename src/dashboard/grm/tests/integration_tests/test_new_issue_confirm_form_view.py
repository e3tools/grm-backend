from unittest.mock import patch

import cryptocode
from django.urls import reverse
from django.utils import timezone

from authentication.factories import UserFactory
from authentication.models import Cdata
from grm.constants import ALERT_CHOICE, ANONYMOUS_CHOICE, EMAIL_CHOICE
from grm.tests.base import DashboardTestCase
from issues.factories import IssueFactory


class NewIssueConfirmFormViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.other_user = UserFactory()
        # Create an unconfirmed issue reported by manager
        self.issue = IssueFactory(reporter=self.manager, confirmed=False, administrative_region=self.root_region)

        self.url = reverse("dashboard:grm:new_issue_step_5", kwargs={"issue": self.issue.id})

    def test_get_allowed_for_manager_reporter(self):
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200

    def test_get_403_if_user_without_role(self):
        resp = self.get(self.url, user=self.other_user)
        assert resp.status_code == 403

    def test_get_404_if_authorized_but_not_reporter(self):
        from authentication.models import GovernmentWorker
        from issues.factories import IssueDepartmentFactory

        dept = IssueDepartmentFactory()
        worker_user = UserFactory()
        GovernmentWorker.objects.create(
            user=worker_user,
            department=dept,
            administrative_region=self.root_region,
        )

        resp = self.get(self.url, user=worker_user)
        assert resp.status_code == 404

    def test_post_by_reporter_confirms_issue_and_sets_internal_code_and_last_activity(self):
        """
        Posting the confirm form as the reporter (manager) should:
          - mark the issue as confirmed
          - set an internal_code
          - update reporter last_activity
          - redirect to the confirmation step 6
        """
        # Prepare POST data matching the fields assembled by NewIssueConfirmForm
        data = {
            "contact_medium": ANONYMOUS_CHOICE,
            "intake_date": self.issue.intake_date.strftime("%d/%m/%Y"),
            "issue_date": self.issue.issue_date.strftime("%d/%m/%Y"),
            "issue_type": str(self.issue.issue_type.id),
            "issue_sub_type": str(self.issue.issue_sub_type.id),
            "category": str(self.issue.category.id),
            "description": self.issue.description,
            "ongoing_issue": "on",
            "administrative_region": str(self.issue.administrative_region.id),
        }
        before = timezone.now()

        resp = self.post(self.url, data=data, user=self.manager)
        # The view performs a redirect on success
        assert resp.status_code in (302, 303)

        # Reload issue and user
        self.issue.refresh_from_db()
        self.manager.refresh_from_db()

        assert self.issue.confirmed is True
        assert self.issue.internal_code is not None
        assert self.manager.last_activity is not None

        # Check last_activity was updated
        assert self.manager.last_activity >= before

    def test_post_denied_for_unrelated_user(self):
        """
        A user without the proper role should receive 403 when attempting to POST.
        """
        data = {"contact_medium": ANONYMOUS_CHOICE}
        resp = self.post(self.url, data=data, user=self.other_user)
        assert resp.status_code == 403

    def test_post_404_if_authorized_but_not_reporter(self):
        """
        A government worker (authorized role) who is not the reporter should get 404 (same as GET behavior).
        """
        from authentication.models import GovernmentWorker
        from issues.factories import IssueDepartmentFactory

        dept = IssueDepartmentFactory()
        worker_user = UserFactory()
        GovernmentWorker.objects.create(
            user=worker_user,
            department=dept,
            administrative_region=self.root_region,
        )

        data = {"contact_medium": ANONYMOUS_CHOICE}
        resp = self.post(self.url, data=data, user=worker_user)
        assert resp.status_code == 404

    @patch('grm.notifications.send_mail_notification')
    def test_post_sends_notification_when_contact_method_exists(self, mock_send_mail):
        """
        Posting the confirm form should send a notification if the issue has a contact_method.
        """
        # Create an issue with contact information
        issue_with_contact = IssueFactory(
            reporter=self.manager,
            confirmed=False,
            administrative_region=self.root_region,
            contact_medium=ALERT_CHOICE,
            contact_method=EMAIL_CHOICE,
            contact_information="citizen@example.com",
        )

        # Encrypt and save contact information to Cdata
        encrypted_contact = cryptocode.encrypt("citizen@example.com", str(issue_with_contact.id))
        Cdata.objects.create(key=str(issue_with_contact.id), data=encrypted_contact)

        url = reverse("dashboard:grm:new_issue_step_5", kwargs={"issue": issue_with_contact.id})

        data = {
            "contact_medium": ALERT_CHOICE,
            "contact_type": EMAIL_CHOICE,
            "contact": "citizen@example.com",
            "intake_date": issue_with_contact.intake_date.strftime("%d/%m/%Y"),
            "issue_date": issue_with_contact.issue_date.strftime("%d/%m/%Y"),
            "issue_type": str(issue_with_contact.issue_type.id),
            "issue_sub_type": str(issue_with_contact.issue_sub_type.id),
            "category": str(issue_with_contact.category.id),
            "description": issue_with_contact.description,
            "ongoing_issue": "on",
            "administrative_region": str(issue_with_contact.administrative_region.id),
        }

        resp = self.post(url, data=data, user=self.manager)
        assert resp.status_code == 302

        # Verify notification was sent
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        assert "citizen@example.com" in str(call_args)
        assert "Issue Created" in call_args[1]['subject']

    @patch('grm.notifications.send_mail_notification')
    def test_post_does_not_send_notification_without_contact_method(self, mock_send_mail):
        """
        Posting the confirm form should not send notification if there's no contact_method.
        """
        data = {
            "contact_medium": ANONYMOUS_CHOICE,
            "intake_date": self.issue.intake_date.strftime("%d/%m/%Y"),
            "issue_date": self.issue.issue_date.strftime("%d/%m/%Y"),
            "issue_type": str(self.issue.issue_type.id),
            "issue_sub_type": str(self.issue.issue_sub_type.id),
            "category": str(self.issue.category.id),
            "description": self.issue.description,
            "ongoing_issue": "on",
            "administrative_region": str(self.issue.administrative_region.id),
        }

        resp = self.post(self.url, data=data, user=self.manager)
        assert resp.status_code == 302

        # Verify no notification was sent
        mock_send_mail.assert_not_called()
