from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from grm.constants import (
    ISSUE_UPDATE_ERROR_MESSAGE,
    ISSUE_UPDATE_SUCCESS_MESSAGE,
    NOT_FOUND_MESSAGE,
    VALIDATION_FAILED_MESSAGE,
)
from grm.utils import reset_sequences
from issues.factories import IssueFactory, IssueStatusFactory, UserFactory


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
        self.other_user = UserFactory()

        # Tokens
        self.reporter_token = Token.objects.create(user=self.reporter_user)
        self.assignee_token = Token.objects.create(user=self.assignee_user)
        self.other_token = Token.objects.create(user=self.other_user)

        # Issue status for testing
        self.new_status = IssueStatusFactory()

        # Issue where reporter and assignee have access
        self.issue = IssueFactory(reporter=self.reporter_user, assignee=self.assignee_user, rating=0)

        self.url = reverse("issues:update-issue", kwargs={"id": self.issue.id})

        self.valid_update_data = {
            'escalate_flag': True,
            'reject_flag': False,
            'rating': 4,
            'escalation_reason': 'Issue requires higher level approval',
            'status': self.new_status.id,
            'research_result': 'Investigation completed. Root cause identified.',
        }

    def authenticate_with_token(self, token=None):
        """Helper method to authenticate client with token."""
        if token is None:
            token = self.reporter_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_reporter_can_update_issue(self):
        """Test that the reporter can update an issue."""
        self.authenticate_with_token()

        response = self.client.patch(self.url, self.valid_update_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)

        # Verify the issue was actually updated
        self.issue.refresh_from_db()
        self.assertTrue(self.issue.escalate_flag)
        self.assertFalse(self.issue.reject_flag)
        self.assertEqual(self.issue.rating, 4)
        self.assertEqual(self.issue.escalation_reason, 'Issue requires higher level approval')
        self.assertEqual(self.issue.status.id, self.new_status.id)
        self.assertEqual(self.issue.research_result, 'Investigation completed. Root cause identified.')

    def test_assignee_can_update_issue(self):
        """Test that the assignee can update an issue."""
        self.authenticate_with_token(self.assignee_token)

        response = self.client.patch(self.url, self.valid_update_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], ISSUE_UPDATE_SUCCESS_MESSAGE)
        self.assertEqual(response.data['data']['id'], self.issue.id)

    def test_other_user_cannot_update_issue(self):
        """Test that other users cannot update issues."""
        self.authenticate_with_token(self.other_token)

        response = self.client.patch(self.url, self.valid_update_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify issue was not updated
        self.issue.refresh_from_db()
        self.assertFalse(self.issue.escalate_flag)
        self.assertEqual(self.issue.rating, 0)  # Default value

    def test_authentication_required_no_credentials(self):
        """Test that authentication is required when no credentials provided."""
        response = self.client.patch(self.url, self.valid_update_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)
        self.assertIn(self.error_messages["authentication"], str(response.data["detail"]))

    def test_nonexistent_issue_returns_404(self):
        """Test that updating a non-existent issue returns 404."""
        self.authenticate_with_token()

        url = reverse("issues:update-issue", kwargs={"id": 9999})
        response = self.client.patch(url, self.valid_update_data, format='json')

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
        self.authenticate_with_token()

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
            response = self.client.patch(self.url, self.valid_update_data, format='json')

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

        self.assertEqual(
            self.client.patch(self.url, self.valid_update_data, format='json').status_code, status.HTTP_200_OK
        )
        self.assertEqual(
            self.client.put(self.url, self.valid_update_data, format='json').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.post(self.url, self.valid_update_data, format='json').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(self.client.delete(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_null_values_are_handled_correctly(self):
        """Test that null values are handled correctly for optional fields."""
        self.authenticate_with_token()

        null_data = {'escalation_reason': None, 'research_result': None, 'status': None}
        response = self.client.patch(self.url, null_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.issue.refresh_from_db()
        self.assertIsNone(self.issue.escalation_reason)
        self.assertIsNone(self.issue.research_result)
        self.assertIsNone(self.issue.status)

    def test_rating_zero_is_valid(self):
        """Test that rating of 0 is valid (default value)."""
        self.authenticate_with_token()

        # First set a rating
        self.client.patch(self.url, {'rating': 3}, format='json')

        # Then try to set it to 0 (should be invalid based on model validators)
        response = self.client.patch(self.url, {'rating': 0}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rating', response.data['errors'])
