import os
import re
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
from grm.constants import (
    ATTACHMENT_CREATE_ERROR_MESSAGE,
    ATTACHMENT_CREATE_SUCCESS_MESSAGE,
    NOT_FOUND_MESSAGE,
)
from grm.utils import reset_sequences
from issues.factories import IssueFactory
from issues.models import IssueAttachment


@pytest.mark.django_db
@override_settings(DEFAULT_FILE_STORAGE='grm.test_storage.InMemoryStorage', LANGUAGE_CODE='en-us')
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

        # A multipart POST request is required for file uploads
        self.valid_data = {
            'file': SimpleUploadedFile(name='test_attachment.txt', content=b'Test content', content_type='text/plain')
        }

    def authenticate_with_token(self):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.reporter_token.key}')

    def test_reporter_can_create_attachment(self):
        """Test that the reporter can create an attachment."""
        self.authenticate_with_token()

        response = self.client.post(self.url, self.valid_data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], ATTACHMENT_CREATE_SUCCESS_MESSAGE)
        self.assertEqual(response.data['data']['uploaded_by']['id'], self.reporter_user.id)

        # Verify that the attachment was actually created in the database
        attachment = IssueAttachment.objects.get(issue=self.issue, uploaded_by=self.reporter_user)
        self.assertIsNotNone(attachment)

        # Extract the file path and filename
        saved_path = attachment.file.name  # e.g., 'attachments/abc123.txt'
        filename = os.path.basename(saved_path)

        # Check that the file is stored under the 'attachments/' directory
        self.assertTrue(saved_path.startswith('attachments/'))

        # Check that the filename ends with '.txt'
        self.assertTrue(filename.endswith('.txt'))

        # Validate that the filename is a valid shortuuid (22 alphanumeric characters)
        uuid_part = filename.replace('.txt', '')
        self.assertTrue(re.match(r'^[A-Za-z0-9]{22}$', uuid_part))

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
        self.assertEqual(response.data['detail'], NOT_FOUND_MESSAGE)

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
        with patch("issues.views.IssueAttachmentCreateAPIView.perform_create", side_effect=RuntimeError("boom")):
            response = self.client.post(self.url, self.valid_data, format='multipart')
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['detail'] == ATTACHMENT_CREATE_ERROR_MESSAGE

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
