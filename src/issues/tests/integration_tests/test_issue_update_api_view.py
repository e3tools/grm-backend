from unittest.mock import patch

import cryptocode
import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
from authentication.models import Cdata
from grm.constants import (
    ALERT_CHOICE,
    EMAIL_CHOICE,
    ISSUE_UPDATE_ERROR_MESSAGE,
    ISSUE_UPDATE_RATING_ERROR_MESSAGE,
    ISSUE_UPDATE_STATUS_ERROR_MESSAGE,
    ISSUE_UPDATE_SUCCESS_MESSAGE,
    NOT_FOUND_MESSAGE,
    PHONE_CHOICE,
    VALIDATION_FAILED_MESSAGE,
)
from grm.utils import reset_sequences
from issues.factories import IssueFactory, IssueStatusFactory
from issues.models import IssueStatusChange


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class IssueUpdateAPIViewTest(APITestCase):
    """Integration tests for the IssueUpdateAPIView."""

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
    }

    def setUp(self):
        """Set up test data and authentication."""

        reset_sequences()

        # Users
        self.reporter_user = UserFactory()
        self.assignee_user = UserFactory()
        self.reporter_assignee_user = UserFactory()  # User who is both reporter and assignee
        self.other_user = UserFactory()

        # Tokens
        self.reporter_token = Token.objects.create(user=self.reporter_user)
        self.assignee_token = Token.objects.create(user=self.assignee_user)
        self.reporter_assignee_token = Token.objects.create(user=self.reporter_assignee_user)
        self.other_token = Token.objects.create(user=self.other_user)

        # Issue status for testing
        self.new_status = IssueStatusFactory()

        # Issue where reporter and assignee are different users
        self.issue = IssueFactory(reporter=self.reporter_user, assignee=self.assignee_user, rating=0, confirmed=True)

        # Issue where user is both reporter and assignee
        self.issue_reporter_assignee = IssueFactory(
            reporter=self.reporter_assignee_user,
            assignee=self.reporter_assignee_user,
            rating=0,
            administrative_region=self.issue.administrative_region,
            confirmed=True,
        )

        self.url = reverse("issues:update-issue", kwargs={"id": self.issue.id})

    def authenticate_with_token(self, token=None):
        """Helper method to authenticate client with token."""
        if token is None:
            token = self.reporter_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_reporter_can_update_issue(self):
        """Test that the reporter can update an issue (excluding restricted fields)."""
        before = timezone.now()
        self.authenticate_with_token()

        # Reporter should be able to update rating and general fields, but not status
        allowed_data = {
            'escalate_flag': True,
            'reject_flag': False,
            'rating': 4,
            'escalation_reason': 'Issue requires higher level approval',
            'research_result': 'Investigation completed. Root cause identified.',
        }

        response = self.client.patch(self.url, allowed_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)

        # Verify the issue was actually updated
        self.issue.refresh_from_db()
        self.assertTrue(self.issue.escalate_flag)
        self.assertFalse(self.issue.reject_flag)
        self.assertEqual(self.issue.rating, 4)
        self.assertEqual(self.issue.escalation_reason, 'Issue requires higher level approval')
        self.assertEqual(self.issue.research_result, 'Investigation completed. Root cause identified.')

        # Check last_activity was updated
        self.reporter_user.refresh_from_db()
        assert self.reporter_user.last_activity >= before

    def test_assignee_can_update_issue(self):
        """Test that the assignee can update an issue (excluding restricted fields)."""
        self.authenticate_with_token(self.assignee_token)

        # Assignee should be able to update status and general fields, but not rating
        allowed_data = {
            'escalate_flag': True,
            'reject_flag': False,
            'escalation_reason': 'Issue requires higher level approval',
            'status': self.new_status.id,
            'research_result': 'Investigation completed. Root cause identified.',
        }

        response = self.client.patch(self.url, allowed_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)
        self.assertEqual(response.data['data']['id'], self.issue.id)

    def test_reporter_cannot_update_status(self):
        """Test that reporter cannot update status field."""
        self.authenticate_with_token(self.reporter_token)

        restricted_data = {'status': self.new_status.id}
        response = self.client.patch(self.url, restricted_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(ISSUE_UPDATE_STATUS_ERROR_MESSAGE, response.data['message'])

        # Verify the issue status was not updated
        self.issue.refresh_from_db()
        self.assertNotEqual(self.issue.status, self.new_status)

    def test_assignee_cannot_update_rating(self):
        """Test that assignee cannot update rating field."""
        self.authenticate_with_token(self.assignee_token)

        restricted_data = {'rating': 5}
        response = self.client.patch(self.url, restricted_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(ISSUE_UPDATE_RATING_ERROR_MESSAGE, response.data['message'])

        # Verify the issue rating was not updated
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.rating, 0)  # Should remain unchanged

    def test_reporter_assignee_can_update_both_restricted_fields(self):
        """Test that user who is both reporter and assignee can update both status and rating."""
        self.authenticate_with_token(self.reporter_assignee_token)

        both_fields_data = {'status': self.new_status.id, 'rating': 5}
        url_reporter_assignee = reverse("issues:update-issue", kwargs={"id": self.issue_reporter_assignee.id})
        response = self.client.patch(url_reporter_assignee, both_fields_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)

        # Verify both fields were updated
        self.issue_reporter_assignee.refresh_from_db()
        self.assertEqual(self.issue_reporter_assignee.status.id, self.new_status.id)
        self.assertEqual(self.issue_reporter_assignee.rating, 5)

    def test_reporter_can_update_other_fields_with_rating(self):
        """Test that reporter can update rating along with other allowed fields."""
        self.authenticate_with_token(self.reporter_token)

        mixed_data = {'rating': 3, 'escalate_flag': True, 'research_result': 'Updated by reporter'}
        response = self.client.patch(self.url, mixed_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.rating, 3)
        self.assertTrue(self.issue.escalate_flag)
        self.assertEqual(self.issue.research_result, 'Updated by reporter')

    def test_assignee_can_update_other_fields_with_status(self):
        """Test that assignee can update status along with other allowed fields."""
        self.authenticate_with_token(self.assignee_token)

        mixed_data = {'status': self.new_status.id, 'reject_flag': True, 'escalation_reason': 'Updated by assignee'}
        response = self.client.patch(self.url, mixed_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status.id, self.new_status.id)
        self.assertTrue(self.issue.reject_flag)
        self.assertEqual(self.issue.escalation_reason, 'Updated by assignee')

    def test_mixed_restricted_fields_in_single_request(self):
        """Test that request with both restricted fields fails if user doesn't have both roles."""
        self.authenticate_with_token(self.reporter_token)  # Reporter trying to update both

        mixed_restricted_data = {
            'rating': 4,  # Allowed for reporter
            'status': self.new_status.id,  # Not allowed for reporter
        }
        response = self.client.patch(self.url, mixed_restricted_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertIn('Only assignees can update the status field', response.data['message'])

    def test_other_user_still_forbidden_with_restrictions(self):
        """Test that other users are still forbidden regardless of field restrictions."""
        self.authenticate_with_token(self.other_token)

        response = self.client.patch(self.url, {'rating': 5}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.patch(self.url, {'status': self.new_status.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authentication_required_no_credentials(self):
        """Test that authentication is required when no credentials provided."""
        response = self.client.patch(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)
        self.assertIn(self.error_messages["authentication"], str(response.data["detail"]))

    def test_nonexistent_issue_returns_404(self):
        """Test that updating a non-existent issue returns 404."""
        self.authenticate_with_token()

        url = reverse("issues:update-issue", kwargs={"id": 9999})
        response = self.client.patch(url, {'escalate_flag': True}, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], NOT_FOUND_MESSAGE)

    def test_partial_update_single_field(self):
        """Test that partial updates work correctly."""
        self.authenticate_with_token()

        partial_data = {'escalate_flag': True}
        response = self.client.patch(self.url, partial_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify only the specified field was updated
        self.issue.refresh_from_db()
        self.assertTrue(self.issue.escalate_flag)
        self.assertEqual(self.issue.rating, 0)  # Should remain unchanged

    def test_rating_validation_below_minimum(self):
        """Test that rating below 1 returns validation error."""
        self.authenticate_with_token()

        invalid_data = {'rating': 0}
        response = self.client.patch(self.url, invalid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], VALIDATION_FAILED_MESSAGE)
        self.assertIn('rating', response.data['errors'])

    def test_rating_validation_above_maximum(self):
        """Test that rating above 5 returns validation error."""
        self.authenticate_with_token()

        invalid_data = {'rating': 6}
        response = self.client.patch(self.url, invalid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], VALIDATION_FAILED_MESSAGE)
        self.assertIn('rating', response.data['errors'])

    def test_invalid_status_id_validation(self):
        """Test that invalid status ID returns validation error."""
        self.authenticate_with_token(self.assignee_token)  # Use assignee token since only they can update status

        invalid_data = {'status': 9999}
        response = self.client.patch(self.url, invalid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data['errors'])

    def test_empty_data_returns_success(self):
        """Test that PATCH with empty data returns success (no changes)."""
        self.authenticate_with_token()

        response = self.client.patch(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_internal_server_error(self):
        """Test internal server error response."""
        self.authenticate_with_token()

        with patch("issues.views.IssueUpdateAPIView.get_object", side_effect=RuntimeError("boom")):
            response = self.client.patch(self.url, {'escalate_flag': True}, format='json')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_ERROR_MESSAGE)

    def test_boolean_field_validation(self):
        """Test that boolean fields accept valid boolean values."""
        self.authenticate_with_token()

        boolean_data = {'escalate_flag': True, 'reject_flag': True}
        response = self.client.patch(self.url, boolean_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertTrue(self.issue.escalate_flag)
        self.assertTrue(self.issue.reject_flag)

    def test_text_field_updates(self):
        """Test that text fields are updated correctly."""
        self.authenticate_with_token()

        text_data = {'escalation_reason': 'Updated escalation reason', 'research_result': 'Updated research result'}
        response = self.client.patch(self.url, text_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.escalation_reason, text_data['escalation_reason'])
        self.assertEqual(self.issue.research_result, text_data['research_result'])

    def test_only_patch_method_allowed(self):
        """Test that only PATCH method is allowed."""
        self.authenticate_with_token()

        allowed_data = {'escalate_flag': True}  # Use non-restricted field

        self.assertEqual(self.client.patch(self.url, allowed_data, format='json').status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.put(self.url, allowed_data, format='json').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.post(self.url, allowed_data, format='json').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(self.client.delete(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_null_values_are_handled_correctly(self):
        """Test that null values are handled correctly for optional fields."""
        self.authenticate_with_token()

        null_data = {'escalation_reason': None, 'research_result': None}
        response = self.client.patch(self.url, null_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertIsNone(self.issue.escalation_reason)
        self.assertIsNone(self.issue.research_result)

    def test_assignee_status_update_closes_previous_and_creates_new_isc(self):
        """When assignee updates status, previous open ISC is closed and a new ISC is created."""
        # Ensure the issue has an initial non-terminal status and an open ISC
        initial_status = IssueStatusFactory(final_status=False, rejected_status=False, threshold_days=1)
        self.issue.status = initial_status
        self.issue.save()

        # There should be an open ISC for the initial status
        isc_before = (
            IssueStatusChange.objects.filter(issue=self.issue, status=initial_status).order_by('-entered_at').first()
        )
        self.assertIsNotNone(isc_before)
        self.assertIsNone(isc_before.exited_at)

        # Authenticate as assignee and update status to new_status
        self.authenticate_with_token(self.assignee_token)
        response = self.client.patch(self.url, {'status': self.new_status.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)

        # Refresh previous ISC and assert it was closed
        isc_before.refresh_from_db()
        self.assertIsNotNone(isc_before.exited_at)

        # New ISC for the new_status should exist and be open
        isc_after = (
            IssueStatusChange.objects.filter(issue=self.issue, status=self.new_status).order_by('-entered_at').first()
        )
        self.assertIsNotNone(isc_after)
        self.assertIsNone(isc_after.exited_at)

    def test_updating_status_to_terminal_sets_resolution_and_does_not_create_isc(self):
        """Updating an issue's status to a terminal status should set resolution_date and not create an ISC."""
        # Create a terminal status and ensure assignee can set it
        terminal_status = IssueStatusFactory(final_status=True, rejected_status=False, threshold_days=1)

        # Authenticate as assignee and update status to terminal
        self.authenticate_with_token(self.assignee_token)
        response = self.client.patch(self.url, {'status': terminal_status.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)

        # Reload issue and assert resolution_date set
        self.issue.refresh_from_db()
        self.assertIsNotNone(self.issue.resolution_date)

        # No open ISC should exist for terminal status; previous open ISC (if any) should have been closed
        iscs = IssueStatusChange.objects.filter(issue=self.issue)
        # There may be previous ISCs but none should be open for the terminal status
        open_iscs = iscs.filter(exited_at__isnull=True)
        self.assertFalse(open_iscs.exists())

    @patch('grm.notifications.send_mail_notification')
    def test_update_issue_status_sends_notification_email(self, mock_send_mail):
        """
        Updating issue status via API should send a notification if contact_method exists.
        """
        self.authenticate_with_token(self.reporter_assignee_token)

        # Create issue with contact information
        issue = IssueFactory(
            reporter=self.reporter_assignee_user,
            assignee=self.reporter_assignee_user,
            confirmed=True,
            contact_medium=ALERT_CHOICE,
            contact_method=EMAIL_CHOICE,
            contact_information='citizen@example.com',
            administrative_region=self.issue.administrative_region,
        )

        # Encrypt and save contact information to Cdata
        encrypted_contact = cryptocode.encrypt("citizen@example.com", str(issue.id))
        Cdata.objects.create(key=str(issue.id), data=encrypted_contact)

        url = reverse('issues:update-issue', kwargs={'id': issue.id})

        data = {
            'status': self.new_status.id,
        }

        response = self.client.patch(url, data, format='json')
        assert response.status_code == 200

        # Verify notification was sent
        mock_send_mail.assert_called_once()
        call_args = mock_send_mail.call_args
        assert "citizen@example.com" in str(call_args)
        assert "Issue Status Updated" in call_args[1]['subject']

    @patch('grm.notifications.send_sms')
    def test_update_issue_status_sends_notification_sms(self, mock_send_sms):
        """
        Updating issue status via API should send a notification if contact_method exists.
        """
        self.authenticate_with_token(self.reporter_assignee_token)

        # Create issue with contact information
        issue = IssueFactory(
            reporter=self.reporter_assignee_user,
            assignee=self.reporter_assignee_user,
            confirmed=True,
            contact_medium=ALERT_CHOICE,
            contact_method=PHONE_CHOICE,
            contact_information='1234567890',
            administrative_region=self.issue.administrative_region,
        )

        # Encrypt and save contact information to Cdata
        encrypted_contact = cryptocode.encrypt("1234567890", str(issue.id))
        Cdata.objects.create(key=str(issue.id), data=encrypted_contact)

        url = reverse('issues:update-issue', kwargs={'id': issue.id})

        data = {
            'status': self.new_status.id,
        }

        response = self.client.patch(url, data, format='json')
        assert response.status_code == 200

        # Verify notification was sent
        mock_send_sms.assert_called_once()
        call_args = mock_send_sms.call_args
        assert "1234567890" in str(call_args)
        assert "The status of your issue has been updated" in call_args[1]['body']
