from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from grm.utils import reset_sequences
from issues.factories import IssueFactory, UserFactory
from issues.models import Comment


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class IssueCommentCreateAPIViewTest(APITestCase):
    """Integration tests for the IssueCommentCreateAPIView."""

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

        # Issue where reporter and assignee have access
        self.issue = IssueFactory(reporter=self.reporter_user, assignee=self.assignee_user)

        self.url = reverse("issues:add-issue-comment", kwargs={"id": self.issue.id})
        self.valid_comment_data = {'comment': 'This is a test comment'}

    def authenticate_with_token(self):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.reporter_token.key}')

    def test_reporter_can_create_comment(self):
        """Test that the reporter can create a comment."""
        self.authenticate_with_token()

        response = self.client.post(self.url, self.valid_comment_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'Comment added successfully.')
        self.assertEqual(response.data['data']['comment'], 'This is a test comment')
        self.assertEqual(response.data['data']['user']['id'], self.reporter_user.id)

        # Verify the comment was actually created
        self.assertTrue(
            Comment.objects.filter(issue=self.issue, user=self.reporter_user, comment='This is a test comment').exists()
        )

    def test_assignee_can_create_comment(self):
        """Test that the assignee can create a comment."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        response = self.client.post(self.url, self.valid_comment_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['user']['id'], self.assignee_user.id)

    def test_other_user_cannot_create_comment(self):
        """Test that other users cannot create comments."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')

        response = self.client.post(self.url, self.valid_comment_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify no comment was created
        self.assertFalse(Comment.objects.filter(issue=self.issue, user=self.other_user).exists())

    def test_authentication_required_no_credentials(self):
        """Test that authentication is required when no credentials provided."""
        response = self.client.post(self.url, self.valid_comment_data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data
        assert self.error_messages["authentication"] in str(response.data["detail"])

    def test_nonexistent_issue_returns_404(self):
        """Test that commenting on a non-existent issue returns 404."""
        self.authenticate_with_token()

        url = reverse("issues:add-issue-comment", kwargs={"id": 9999})
        response = self.client.post(url, self.valid_comment_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], 'Not found.')

    def test_empty_comment_validation_error(self):
        """Test that empty comments return validation error."""
        self.authenticate_with_token()

        invalid_data = {'comment': ''}
        response = self.client.post(self.url, invalid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], 'Validation failed.')
        self.assertIn('comment', response.data['errors'])

    def test_internal_server_error(self):
        """Test internal server error response."""

        self.authenticate_with_token()
        with patch("issues.views.IssueCommentCreateAPIView.perform_create", side_effect=RuntimeError("boom")):
            response = self.client.post(self.url, self.valid_comment_data, format='json')
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['detail'] == 'An error occurred while creating the comment.'

    def test_whitespace_only_comment_validation_error(self):
        """Test that whitespace-only comments return validation error."""
        self.authenticate_with_token()

        invalid_data = {'comment': '   \n\t   '}
        response = self.client.post(self.url, invalid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('comment', response.data['errors'])

    def test_missing_comment_field_validation_error(self):
        """Test that missing comment field returns validation error."""
        self.authenticate_with_token()

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], 'Validation failed.')
        self.assertIn('comment', response.data['errors'])

    def test_comment_text_is_trimmed(self):
        """Test that comment text is properly trimmed of whitespace."""
        self.authenticate_with_token()

        comment_data = {'comment': '  This is a comment with spaces  '}
        response = self.client.post(self.url, comment_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['comment'], 'This is a comment with spaces')

        # Verify in database
        comment = Comment.objects.get(id=response.data['data']['id'])
        self.assertEqual(comment.comment, 'This is a comment with spaces')

    def test_comment_max_length_validation(self):
        """Test that comments exceeding max length return validation error."""
        self.authenticate_with_token()

        long_comment = 'A' * 1001  # Exceeds max_length of 1000
        comment_data = {'comment': long_comment}

        response = self.client.post(self.url, comment_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('comment', response.data['errors'])

    def test_comment_response_structure(self):
        """Test that the comments response format matches expected structure."""
        self.authenticate_with_token()
        response = self.client.post(self.url, self.valid_comment_data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        data = response.data["data"]
        expected_fields = ["id", "comment", "user", "issue", "due_date"]
        for field in expected_fields:
            assert field in data

        assert isinstance(data["id"], int)
        assert isinstance(data["comment"], str)
        assert isinstance(data["user"], dict)
        assert isinstance(data["issue"], int)
        assert isinstance(data["due_date"], str)

    def test_get_method_only_allowed(self):
        self.authenticate_with_token()
        assert self.client.post(self.url, self.valid_comment_data, format='json').status_code == status.HTTP_201_CREATED
        assert (
            self.client.put(self.url, self.valid_comment_data, format='json').status_code
            == status.HTTP_405_METHOD_NOT_ALLOWED
        )
        assert self.client.delete(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert (
            self.client.patch(self.url, self.valid_comment_data, format='json').status_code
            == status.HTTP_405_METHOD_NOT_ALLOWED
        )
        assert self.client.get(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
