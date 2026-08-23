from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
from grm.constants import ATTACHMENT_CREATE_ERROR_MESSAGE, NOT_FOUND_MESSAGE
from grm.utils import reset_sequences
from issues.factories import IssueAttachmentFactory, IssueFactory
from issues.models import IssueAttachment


@pytest.mark.django_db
@override_settings(DEFAULT_FILE_STORAGE='grm.test_storage.InMemoryStorage', LANGUAGE_CODE='en-us')
class IssueAttachmentDeleteAPIViewTest(APITestCase):
    """Integration tests for the IssueAttachmentDeleteAPIView."""

    def setUp(self):
        reset_sequences()

        # Users
        self.reporter_user = UserFactory()
        self.assignee_user = UserFactory()
        self.other_user = UserFactory()

        # Tokens
        self.reporter_token = Token.objects.create(user=self.reporter_user)
        self.assignee_token = Token.objects.create(user=self.assignee_user)
        self.other_token = Token.objects.create(user=self.other_user)

        # Issue and attachment
        self.issue = IssueFactory(reporter=self.reporter_user, assignee=self.assignee_user)
        self.attachment = IssueAttachmentFactory(issue=self.issue, uploaded_by=self.reporter_user)

        self.url = reverse("issues:delete-issue-attachment", kwargs={"id": self.attachment.id})

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_reporter_can_delete_attachment(self):
        """Reporter of the issue can delete attachments."""
        before = timezone.now()
        self.authenticate(self.reporter_token)
        response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueAttachment.objects.filter(id=self.attachment.id).exists()

        # Check last_activity was updated
        self.reporter_user.refresh_from_db()
        assert self.reporter_user.last_activity >= before

    def test_assignee_can_delete_attachment(self):
        """Assignee of the issue can delete attachments."""
        self.authenticate(self.assignee_token)
        response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueAttachment.objects.filter(id=self.attachment.id).exists()

    def test_other_user_cannot_delete_attachment(self):
        """User who is neither reporter nor assignee cannot delete attachments."""
        self.authenticate(self.other_token)
        response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert IssueAttachment.objects.filter(id=self.attachment.id).exists()

    def test_authentication_required(self):
        """Unauthenticated users cannot delete attachments."""
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert IssueAttachment.objects.filter(id=self.attachment.id).exists()

    def test_nonexistent_attachment_returns_404(self):
        """Deleting non-existent attachment returns 404."""
        self.authenticate(self.reporter_token)
        url = reverse("issues:delete-issue-attachment", kwargs={"id": 9999})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        self.assertEqual(response.data['detail'], NOT_FOUND_MESSAGE)

    def test_delete_removes_file_from_storage(self):
        """Deleting attachment removes the file from storage."""
        self.authenticate(self.reporter_token)

        with override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage'):
            attachment = IssueAttachmentFactory(issue=self.issue, uploaded_by=self.reporter_user)
            url = reverse("issues:delete-issue-attachment", kwargs={"id": attachment.id})

            # Get the file path before deletion
            file_path = attachment.file.path
            assert attachment.file.storage.exists(file_path)

            # Delete the attachment
            response = self.client.delete(url)

            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert not IssueAttachment.objects.filter(id=attachment.id).exists()

    def test_multiple_attachments_only_one_deleted(self):
        """Deleting one attachment doesn't affect other attachments of same issue."""
        # Create another attachment for the same issue
        other_attachment = IssueAttachmentFactory(issue=self.issue, uploaded_by=self.assignee_user)

        self.authenticate(self.reporter_token)
        response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueAttachment.objects.filter(id=self.attachment.id).exists()
        assert IssueAttachment.objects.filter(id=other_attachment.id).exists()

    def test_internal_server_error(self):
        """Simulate an unexpected exception inside the view."""
        self.authenticate(self.reporter_token)
        with patch("issues.views.IssueAttachmentDeleteAPIView.perform_destroy", side_effect=RuntimeError("boom")):
            response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['detail'] == ATTACHMENT_CREATE_ERROR_MESSAGE

    def test_delete_method_only_allowed(self):
        """Ensure only DELETE is permitted."""
        self.authenticate(self.reporter_token)
        assert self.client.post(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert self.client.put(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert self.client.patch(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert self.client.get(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_attachment_uploaded_by_other_user(self):
        """User can delete attachment uploaded by another user (if they have access to issue)."""
        # Create attachment uploaded by other user
        other_attachment = IssueAttachmentFactory(issue=self.issue, uploaded_by=self.other_user)
        url = reverse("issues:delete-issue-attachment", kwargs={"id": other_attachment.id})

        # Reporter can still delete it
        self.authenticate(self.reporter_token)
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not IssueAttachment.objects.filter(id=other_attachment.id).exists()

    def test_idempotent_delete_returns_404_on_second_attempt(self):
        """Attempting to delete already deleted attachment returns 404."""
        self.authenticate(self.reporter_token)

        # First delete succeeds
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Second delete returns 404
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
