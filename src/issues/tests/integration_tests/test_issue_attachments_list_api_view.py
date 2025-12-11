from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
from grm.constants import ATTACHMENT_RETRIEVE_ERROR_MESSAGE, NOT_FOUND_MESSAGE
from grm.utils import reset_sequences
from issues.factories import IssueAttachmentFactory, IssueFactory
from issues.models import IssueAttachment


@pytest.mark.django_db
@override_settings(DEFAULT_FILE_STORAGE='grm.test_storage.InMemoryStorage', LANGUAGE_CODE='en-us')
class IssueAttachmentsListAPIViewTest(APITestCase):
    """
    Test cases for the IssueAttachment list API endpoint using Token Authentication.

    This test class covers scenarios including authentication, access control
    (only reporter/assignee can see attachments), data retrieval, pagination,
    response format, and performance with large datasets.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
        "permission_denied": "You do not have permission to perform this action.",
    }

    def setUp(self):
        """Set up test data, users, token, issue, and attachments for each test."""
        reset_sequences()
        # Users
        self.reporter = UserFactory()
        self.assignee = UserFactory()
        self.other_user = UserFactory()

        # Tokens
        self.reporter_token = Token.objects.create(user=self.reporter)
        self.assignee_token = Token.objects.create(user=self.assignee)
        self.other_token = Token.objects.create(user=self.other_user)

        # Issue where reporter and assignee have access
        self.issue = IssueFactory(reporter=self.reporter, assignee=self.assignee)

        # URL for attachments list
        self.url = reverse("issues:list-issue-attachments", args=[self.issue.id])

        # Attachments
        self.attachment1 = IssueAttachmentFactory(issue=self.issue, uploaded_by=self.reporter)
        self.attachment2 = IssueAttachmentFactory(issue=self.issue, uploaded_by=self.assignee)

    def authenticate_with_token(self, token):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    # -----------------------------
    # Authentication tests
    # -----------------------------
    def test_authentication_required_no_credentials(self):
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert self.error_messages["authentication"] in str(response.data["detail"])

    def test_authentication_required_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token invalid_token_123")
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert self.error_messages["invalid_token"] in str(response.data["detail"])

    # -----------------------------
    # Permission tests
    # -----------------------------
    def test_reporter_can_access_attachments(self):
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_assignee_can_access_attachments(self):
        self.authenticate_with_token(self.assignee_token)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_other_user_cannot_access_attachments(self):
        self.authenticate_with_token(self.other_token)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert self.error_messages["permission_denied"] in str(response.data["detail"])

    def test_nonexistent_issue_returns_404(self):
        """Test that requesting attachments for non-existent issue returns 404."""
        self.authenticate_with_token(self.reporter_token)
        url = reverse("issues:list-issue-attachments", kwargs={"id": 9999})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        self.assertEqual(response.data['detail'], NOT_FOUND_MESSAGE)

    def test_internal_server_error(self):
        """Test internal server error response."""
        self.authenticate_with_token(self.reporter_token)
        with patch("issues.views.IssueAttachmentsListAPIView.get_queryset", side_effect=RuntimeError("boom")):
            response = self.client.get(self.url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["detail"] == ATTACHMENT_RETRIEVE_ERROR_MESSAGE

    # -----------------------------
    # Data retrieval tests
    # -----------------------------
    def test_successful_list_retrieval_paginated(self):
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)
        data = response.data
        assert response.status_code == status.HTTP_200_OK
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data
        assert data["count"] == 2
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 2

    def test_empty_list_when_no_attachments(self):
        IssueAttachment.objects.all().delete()
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
        assert len(response.data["results"]) == 0

    def test_filter_by_created_date_returns_only_recent_attachments(self):
        """Test filtering attachments by created_date only returns those created after the given datetime."""
        self.authenticate_with_token(self.reporter_token)

        # Force attachment1 to be older than attachment2
        self.attachment1.created_date = self.attachment1.created_date.replace(year=self.attachment1.created_date.year - 1)
        self.attachment1.save(update_fields=["created_date"])

        # Filter by date after attachment1
        created_after = self.attachment1.created_date.isoformat().replace("+00:00", "Z")
        response = self.client.get(self.url, {"created_date": created_after})

        assert response.status_code == status.HTTP_200_OK
        attachments_ids = {i["id"] for i in response.data["results"]}
        assert self.attachment2.id in attachments_ids
        assert self.attachment1.id not in attachments_ids

    def test_filter_by_updated_date_returns_only_recently_updated_attachments(self):
        """Test filtering attachments by updated_date only returns those updated after the given datetime."""
        self.authenticate_with_token(self.reporter_token)

        # Force attachment1 to be updated much earlier
        old_updated_date = self.attachment1.updated_date.replace(year=self.attachment1.updated_date.year - 1)
        IssueAttachment.objects.filter(id=self.attachment1.id).update(updated_date=old_updated_date)
        self.attachment1.refresh_from_db()

        updated_after = self.attachment1.updated_date.isoformat().replace("+00:00", "Z")
        response = self.client.get(self.url, {"updated_date": updated_after})

        assert response.status_code == status.HTTP_200_OK
        attachments_ids = {i["id"] for i in response.data["results"]}
        assert self.attachment2.id in attachments_ids
        assert self.attachment1.id not in attachments_ids

    def test_filter_by_deleted_date_returns_only_recently_deleted_attachments(self):
        """Test filtering attachments by deleted_date only returns those updated after the given datetime."""
        self.authenticate_with_token(self.reporter_token)

        # Force attachment1 to be deleted much earlier
        IssueAttachment.objects.filter(id=self.attachment1.id).update(deleted_date=timezone.now().date())
        self.attachment1.refresh_from_db()
        deleted_after = self.attachment1.deleted_date.replace(year=self.attachment1.deleted_date.year - 1)
        deleted_after = deleted_after.isoformat().replace("+00:00", "Z")
        response = self.client.get(self.url, {"deleted_date": deleted_after})

        assert response.status_code == status.HTTP_200_OK
        attachments_ids = {i["id"] for i in response.data["results"]}
        assert self.attachment2.id not in attachments_ids
        assert self.attachment1.id in attachments_ids

    # -----------------------------
    # Response format validation
    # -----------------------------
    def test_attachments_response_structure(self):
        """Test that the attachments response format matches expected structure."""
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert isinstance(results, list)
        first_attachment = results[0]
        expected_fields = ["id", "uploaded_by", "issue", "file", "created_date", "deleted_date"]
        for field in expected_fields:
            assert field in first_attachment

        assert isinstance(first_attachment["id"], int)
        assert isinstance(first_attachment["file"], str)
        assert isinstance(first_attachment["uploaded_by"], dict)
        assert isinstance(first_attachment["issue"], dict)
        assert isinstance(first_attachment["created_date"], str)

    # -----------------------------
    # Performance & pagination
    # -----------------------------
    def test_large_dataset_paginated(self):
        IssueAttachmentFactory.create_batch(50, issue=self.issue, uploaded_by=self.reporter)
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 52  # 2 original + 50 news
        assert len(response.data["results"]) == 20  # Default page size
        assert response.data["next"] is not None
        assert response.data["previous"] is None

        # Verify ordering by -created_date
        dates = [issue['created_date'] for issue in response.data['results']]
        assert dates == sorted(dates, reverse=True)

    # -----------------------------
    # Allowed methods
    # -----------------------------
    def test_get_method_only_allowed(self):
        self.authenticate_with_token(self.reporter_token)
        assert self.client.post(self.url, {}).status_code == 405
        assert self.client.put(self.url, {}).status_code == 405
        assert self.client.delete(self.url).status_code == 405
        assert self.client.patch(self.url, {}).status_code == 405
        assert self.client.get(self.url).status_code == 200
