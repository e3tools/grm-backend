from unittest.mock import patch

import pytest
from django.core.files.storage import FileSystemStorage
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from attachments.models import IssueAttachment
from grm.utils import reset_sequences
from issues.factories import IssueAttachmentFactory, IssueFactory, UserFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class IssueAttachmentCreateAPIViewTest(APITestCase):
    """Integration tests for the IssueAttachmentCreateAPIView."""

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

        # Create an issue with reporter and assignee have access
        self.issue = IssueFactory(
            reporter=self.reporter_user,
            assignee=self.assignee_user,
        )

        self.url = reverse("issues:add-issue-attachment", kwargs={"id": self.issue.id})
        attachment_instance = IssueAttachmentFactory(issue=self.issue)

        # A multipart POST request is required for file uploads
        self.valid_data = {'file': attachment_instance.file.file}

    def authenticate_with_token(self):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.reporter_token.key}')

    @patch.object(FileSystemStorage, 'save', return_value='test_attachment.txt')
    def test_reporter_can_create_attachment(self, mock_save):
        """Test that the reporter can create an attachment."""
        self.authenticate_with_token()

        response = self.client.post(self.url, self.valid_data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'Attachment uploaded successfully.')
        self.assertEqual(response.data['data']['file'].split('/')[-1], 'test_attachment.txt')
        self.assertEqual(response.data['data']['uploaded_by']['id'], self.reporter_user.id)

        # Verify the attachment was actually created
        self.assertTrue(IssueAttachment.objects.filter(issue=self.issue, uploaded_by=self.reporter_user).exists())

    def test_assignee_can_create_attachment(self):
        """Test that the assignee can create an attachment."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        response = self.client.post(self.url, self.valid_data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['uploaded_by']['id'], self.assignee_user.id)

    def test_other_user_cannot_create_attachment(self):
        """Test that other users cannot create attachment."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')

        response = self.client.post(self.url, self.valid_data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify no attachment was created
        self.assertFalse(IssueAttachment.objects.filter(issue=self.issue, uploaded_by=self.other_user).exists())

    def test_authentication_required_no_credentials(self):
        """Test that authentication is required when no credentials provided."""
        response = self.client.post(self.url, self.valid_data, format='multipart')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data
        assert self.error_messages["authentication"] in str(response.data["detail"])

    def test_nonexistent_issue_returns_404(self):
        """Test that attaching on a non-existent issue returns 404."""
        self.authenticate_with_token()

        url = reverse("issues:add-issue-attachment", kwargs={"id": 9999})
        response = self.client.post(url, self.valid_data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], 'Not found.')

    def test_empty_attachment_validation_error(self):
        """Test that empty attachments return validation error."""
        self.authenticate_with_token()

        invalid_data = {'file': ''}
        response = self.client.post(self.url, invalid_data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data['errors'])

    def test_internal_server_error(self):
        """Test internal server error response."""
        self.authenticate_with_token()
        with patch("issues.views.IssueAttachmentCreateAPIView.get_issue", side_effect=RuntimeError("boom")):
            response = self.client.post(self.url, self.valid_data, format='multipart')
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['detail'] == 'An error occurred during file upload.'

    def test_missing_attachment_field_validation_error(self):
        """Test that missing attachment field returns validation error."""
        self.authenticate_with_token()

        response = self.client.post(self.url, {}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data['errors'])

    def test_attachment_response_structure(self):
        """Test that the attachments response format matches expected structure."""
        self.authenticate_with_token()
        response = self.client.post(self.url, self.valid_data, format='multipart')

        assert response.status_code == status.HTTP_201_CREATED
        data = response.data["data"]
        expected_fields = ["id", "uploaded_by", "issue", "file", "created_date"]
        for field in expected_fields:
            assert field in data

        assert isinstance(data["id"], int)
        assert isinstance(data["file"], str)
        assert isinstance(data["uploaded_by"], dict)
        assert isinstance(data["issue"], dict)
        assert isinstance(data["created_date"], str)

    def test_post_method_only_allowed(self):
        """Test that only POST is allowed."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.client.put(self.url, self.valid_data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.client.patch(self.url, self.valid_data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
