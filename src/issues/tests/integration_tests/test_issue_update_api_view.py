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
    ISSUE_UPDATE_APPEAL_STATUS_ERROR_MESSAGE,
    ISSUE_UPDATE_ERROR_MESSAGE,
    ISSUE_UPDATE_ESCALATE_ERROR_MESSAGE,
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
        self.rejected_status = IssueStatusFactory(rejected_status=True)
        self.final_status = IssueStatusFactory(final_status=True)

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
        self.authenticate_with_token(self.reporter_token)

        # Reporter should be able to update rating
        response = self.client.patch(self.url, {'rating': 4}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)

        # Verify the issue was actually updated
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.rating, 4)

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
        }

        response = self.client.patch(self.url, allowed_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)
        self.assertEqual(response.data['data']['id'], self.issue.id)

    def test_reporter_cannot_update_escalate_flag(self):
        """Test that reporter cannot update escalate_flag field."""
        self.authenticate_with_token(self.reporter_token)

        restricted_data = {'escalate_flag': True}
        response = self.client.patch(self.url, restricted_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(ISSUE_UPDATE_ESCALATE_ERROR_MESSAGE, response.data['message'])

        # Verify the issue escalate_flag was not updated
        self.issue.refresh_from_db()
        self.assertFalse(self.issue.escalate_flag)

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
        """Test that user who is both reporter and assignee can update status, rating and escalate_flag."""
        self.authenticate_with_token(self.reporter_assignee_token)

        both_fields_data = {'status': self.new_status.id, 'rating': 5, 'escalate_flag': True}
        url_reporter_assignee = reverse("issues:update-issue", kwargs={"id": self.issue_reporter_assignee.id})
        response = self.client.patch(url_reporter_assignee, both_fields_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)

        # Verify all fields were updated
        self.issue_reporter_assignee.refresh_from_db()
        self.assertEqual(self.issue_reporter_assignee.status.id, self.new_status.id)
        self.assertEqual(self.issue_reporter_assignee.rating, 5)
        self.assertTrue(self.issue_reporter_assignee.escalate_flag)

    def test_assignee_can_update_escalate_flag(self):
        """Test that assignee can update escalate_flag field."""
        self.authenticate_with_token(self.assignee_token)

        data = {'escalate_flag': True}
        response = self.client.patch(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)

        # Verify the issue escalate_flag was updated
        self.issue.refresh_from_db()
        self.assertTrue(self.issue.escalate_flag)

    def test_assignee_can_update_other_fields_with_status(self):
        """Test that assignee can update status along with other allowed fields."""
        self.authenticate_with_token(self.assignee_token)

        mixed_data = {'status': self.rejected_status.id, 'reject_flag': True, 'reject_reason': 'Rejected by assignee'}
        response = self.client.patch(self.url, mixed_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status.id, self.rejected_status.id)
        self.assertTrue(self.issue.reject_flag)
        self.assertEqual(self.issue.reject_reason, 'Rejected by assignee')

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

    def test_partial_update_reject_flag(self):
        """Test that partial updates work correctly."""
        self.authenticate_with_token(self.assignee_token)
        partial_data = {'status': self.rejected_status.id, 'reject_flag': True}
        response = self.client.patch(self.url, partial_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify only the specified field was updated
        self.issue.refresh_from_db()
        self.assertTrue(self.issue.reject_flag)
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

    def test_only_patch_method_allowed(self):
        """Test that only PATCH method is allowed."""
        self.authenticate_with_token()

        allowed_data = {'reject_flag': True}  # Use non-restricted field

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

    def test_patch_appeal_status_by_assignee(self):
        """Test that assignee can update appeal_status field."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        data = {'appeal_status': True}

        response = self.client.patch(self.url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['appeal_status'] is True

        # Verify data was updated
        self.issue.refresh_from_db()
        assert self.issue.appeal_status is True

    def test_patch_appeal_status_false_by_assignee_is_forbidden(self):
        """Test that appeal_status cannot be set to False via IssueUpdateAPIView."""
        # Set initial state to True
        self.issue.appeal_status = True
        self.issue.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        data = {'appeal_status': False}

        response = self.client.patch(self.url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['message'] == VALIDATION_FAILED_MESSAGE
        assert 'appeal_status' in response.data['errors']

        # Verify appeal_status was NOT changed
        self.issue.refresh_from_db()
        assert self.issue.appeal_status is True

    def test_patch_appeal_status_true_when_already_true_is_forbidden(self):
        """Test that setting appeal_status to True when it's already True is rejected."""
        self.issue.appeal_status = True
        self.issue.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        data = {'appeal_status': True}

        response = self.client.patch(self.url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'appeal_status' in response.data['errors']

    def test_patch_appeal_status_by_reporter_forbidden(self):
        """Test that reporter cannot update appeal_status field."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.reporter_token.key}')

        data = {'appeal_status': True}

        response = self.client.patch(self.url, data, format='json')

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        self.assertEqual(response.data['message'], ISSUE_UPDATE_APPEAL_STATUS_ERROR_MESSAGE)

    def test_patch_appeal_status_by_other_user_forbidden(self):
        """Test that other users cannot update appeal_status field."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')

        data = {'appeal_status': True}

        response = self.client.patch(self.url, data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_status_and_appeal_status_by_assignee(self):
        """Test that assignee can update both status and appeal_status."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        data = {'status': self.new_status.id, 'appeal_status': True}

        response = self.client.patch(self.url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['status']['id'] == self.new_status.id
        assert response.data['data']['appeal_status'] is True

        # Verify data was updated
        self.issue.refresh_from_db()
        assert self.issue.status_id == self.new_status.id
        assert self.issue.appeal_status is True

    def test_patch_appeal_status_triggers_notification(self):
        """Test that appeal_status change triggers notification."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        with patch('issues.views.send_issue_notification') as mock_notify:
            data = {'appeal_status': True}

            response = self.client.patch(self.url, data, format='json')

            assert response.status_code == status.HTTP_200_OK
            # Verify notification was called for appealed
            calls = [call for call in mock_notify.call_args_list if 'appealed' in str(call)]
            assert len(calls) > 0

    def test_patch_no_appeal_status_change_no_notification(self):
        """Test that no notification is sent if appeal_status doesn't change."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        # Set initial state to True
        self.issue.appeal_status = True
        self.issue.save()

        with patch('issues.views.send_issue_notification') as mock_notify:
            data = {'appeal_status': True}  # Same as current

            response = self.client.patch(self.url, data, format='json')

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            # Verify notification was NOT called for appealed
            calls = [call for call in mock_notify.call_args_list if 'appealed' in str(call)]
            assert len(calls) == 0

    def test_patch_response_includes_all_issue_fields(self):
        """Test that response includes all issue detail fields."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        data = {'appeal_status': True}
        response = self.client.patch(self.url, data, format='json')

        assert response.status_code == status.HTTP_200_OK

        # Verify response structure
        assert 'message' in response.data
        assert 'data' in response.data

        issue_data = response.data['data']
        assert 'id' in issue_data
        assert 'status' in issue_data
        assert 'appeal_status' in issue_data
        assert 'category' in issue_data
        assert 'issue_type' in issue_data
        assert 'administrative_region' in issue_data
        assert 'intake_date' in issue_data
        assert 'created_date' in issue_data
        assert 'updated_date' in issue_data

    def test_reject_flag_true_clears_research_result(self):
        """When reject_flag is set to True, research_result must be cleared."""
        self.authenticate_with_token(self.assignee_token)
        self.issue.research_result = 'Some prior research'
        self.issue.save()
        partial_data = {'status': self.rejected_status.id, 'reject_flag': True}
        response = self.client.patch(self.url, partial_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        self.issue.refresh_from_db()
        assert self.issue.reject_flag is True
        assert self.issue.research_result is None

    def test_reject_flag_false_does_not_clear_research_result(self):
        """When reject_flag is set to False, research_result is preserved."""
        self.authenticate_with_token(self.reporter_token)

        self.issue.research_result = 'Some prior research'
        self.issue.reject_flag = False
        self.issue.save()

        response = self.client.patch(self.url, {'reject_flag': False}, format='json')

        assert response.status_code == status.HTTP_200_OK
        self.issue.refresh_from_db()
        assert self.issue.reject_flag is False
        assert self.issue.research_result == 'Some prior research'

    def test_non_rejected_status_clears_reject_reason_and_reject_flag(self):
        """Changing to a non-rejected status clears reject_reason and reject_flag."""
        self.authenticate_with_token(self.assignee_token)

        # Pre-populate rejection fields
        self.issue.reject_reason = 'Invalid report'
        self.issue.reject_flag = True
        self.issue.save()

        # new_status is created by IssueStatusFactory with rejected_status=False by default
        assert self.new_status.rejected_status is False

        response = self.client.patch(self.url, {'status': self.new_status.id}, format='json')

        assert response.status_code == status.HTTP_200_OK
        self.issue.refresh_from_db()
        assert self.issue.status_id == self.new_status.id
        assert self.issue.reject_reason is None
        assert self.issue.reject_flag is False

    def test_rejected_status_preserves_reject_reason_and_reject_flag(self):
        """Changing to a rejected status does NOT clear reject_reason or reject_flag."""
        self.authenticate_with_token(self.assignee_token)

        rejected_status = IssueStatusFactory(rejected_status=True)

        self.issue.reject_reason = 'Invalid report'
        self.issue.reject_flag = True
        self.issue.save()

        response = self.client.patch(self.url, {'status': rejected_status.id}, format='json')

        assert response.status_code == status.HTTP_200_OK
        self.issue.refresh_from_db()
        assert self.issue.status_id == rejected_status.id
        assert self.issue.reject_reason == 'Invalid report'
        assert self.issue.reject_flag is True

    def test_research_result_and_reject_reason_mutually_exclusive(self):
        """It is not possible to send the value in research_result and reject_reason to the view at the same time."""
        self.authenticate_with_token(self.assignee_token)
        final_status = IssueStatusFactory(final_status=True)

        data = {'status': final_status.id, 'research_result': 'Some prior research', 'reject_reason': 'Reject reason'}
        response = self.client.patch(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        errors_str = str(response.data.get('errors', ''))
        self.assertIn('research_result and reject_reason', errors_str)

    def test_research_result_requires_final_status(self):
        """You cannot send research_result with a value if the new status is not final_status."""
        self.authenticate_with_token(self.assignee_token)
        non_final_status = IssueStatusFactory(final_status=False)

        data = {'status': non_final_status.id, 'research_result': 'Some prior research'}
        response = self.client.patch(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('research_result', response.data.get('errors', {}))

    def test_research_result_accepted_with_final_status(self):
        """You can only send research_result with a value if the new status.final_status is True."""
        self.authenticate_with_token(self.assignee_token)
        final_status = IssueStatusFactory(final_status=True)

        data = {'status': final_status.id, 'research_result': 'Detalles de la investigación'}
        response = self.client.patch(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.research_result, 'Detalles de la investigación')

    def test_reject_reason_with_flag_requires_final_status(self):
        """You can only send reject_reason with value and reject_flag True if the new status.rejected_status is True."""
        self.authenticate_with_token(self.assignee_token)

        data = {'status': self.new_status.id, 'reject_flag': True, 'reject_reason': 'Reject reason'}
        response = self.client.patch(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('reject_reason', response.data.get('errors', {}))

    def test_reject_reason_with_flag_accepted_with_final_status(self):
        """Success sending reject_reason with reject_flag True if final_status is True."""
        self.authenticate_with_token(self.assignee_token)
        final_rejected_status = IssueStatusFactory(final_status=True, rejected_status=True)

        data = {'status': final_rejected_status.id, 'reject_flag': True, 'reject_reason': 'Reject reason'}
        response = self.client.patch(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.reject_reason, 'Reject reason')
        self.assertTrue(self.issue.reject_flag)
