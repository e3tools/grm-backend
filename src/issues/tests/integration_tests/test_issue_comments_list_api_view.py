from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from grm.utils import reset_sequences
from issues.factories import CommentFactory, IssueFactory, UserFactory
from issues.models import Comment


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class IssueCommentsListAPIViewTest(APITestCase):
    """
    Test cases for the IssueComments list API endpoint using Token Authentication.

    This test class covers scenarios including authentication, access control
    (only reporter/assignee can see comments), data retrieval, pagination,
    response format, and performance with large datasets.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
        "permission_denied": "You do not have permission to perform this action.",
    }

    def setUp(self):
        """Set up test data, users, token, issue, and comments for each test."""
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

        # URL for comments list
        self.url = reverse("issues:list-issue-comments", args=[self.issue.id])

        # Comments
        self.comment1 = CommentFactory(issue=self.issue, user=self.reporter)
        self.comment2 = CommentFactory(issue=self.issue, user=self.assignee)

    def authenticate_with_token(self, token):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    # -----------------------------
    # Authentication tests
    # -----------------------------
    def test_authentication_required_no_credentials(self):
        response = self.client.get(self.url)
        assert response.status_code == 401
        assert self.error_messages["authentication"] in str(response.data["detail"])

    def test_authentication_required_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token invalid_token_123")
        response = self.client.get(self.url)
        assert response.status_code == 401
        assert self.error_messages["invalid_token"] in str(response.data["detail"])

    # -----------------------------
    # Permission tests
    # -----------------------------
    def test_reporter_can_access_comments(self):
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_assignee_can_access_comments(self):
        self.authenticate_with_token(self.assignee_token)
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_other_user_cannot_access_comments(self):
        self.authenticate_with_token(self.other_token)
        response = self.client.get(self.url)
        assert response.status_code == 403
        assert self.error_messages["permission_denied"] in str(response.data["detail"])

    def test_nonexistent_issue_returns_404(self):
        """Test that requesting comments for non-existent issue returns 404."""
        self.authenticate_with_token(self.reporter_token)
        url = reverse("issues:list-issue-comments", kwargs={"id": 9999})
        response = self.client.get(url)

        assert response.status_code == 404

    def test_internal_server_error(self):
        """Test internal server error response."""
        self.authenticate_with_token(self.reporter_token)
        with patch("issues.views.IssueCommentsListAPIView.get_queryset", side_effect=RuntimeError("boom")):
            response = self.client.get(self.url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["detail"] == "An error occurred while retrieving issue comments."

    # -----------------------------
    # Data retrieval tests
    # -----------------------------
    def test_successful_list_retrieval_paginated(self):
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)
        data = response.data
        assert response.status_code == 200
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data
        assert data["count"] == 2
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 2

    def test_empty_list_when_no_comments(self):
        Comment.objects.all().delete()
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["count"] == 0
        assert len(response.data["results"]) == 0

    # -----------------------------
    # Response format validation
    # -----------------------------
    def test_comments_response_structure(self):
        """Test that the comments response format matches expected structure."""
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)

        assert response.status_code == 200
        results = response.data["results"]
        assert isinstance(results, list)
        first_comment = results[0]
        expected_fields = ["id", "comment", "user", "issue", "due_date"]
        for field in expected_fields:
            assert field in first_comment

        assert isinstance(first_comment["id"], int)
        assert isinstance(first_comment["comment"], str)
        assert isinstance(first_comment["user"], dict)
        assert isinstance(first_comment["issue"], int)
        assert isinstance(first_comment["due_date"], str)

    # -----------------------------
    # Performance & pagination
    # -----------------------------
    def test_large_dataset_paginated(self):
        CommentFactory.create_batch(50, issue=self.issue, user=self.reporter)
        self.authenticate_with_token(self.reporter_token)
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["count"] == 52  # 2 original + 50 news
        assert len(response.data["results"]) == 20  # Default page size
        assert response.data["next"] is not None
        assert response.data["previous"] is None

        # Verify ordering by -due_date
        dates = [issue['due_date'] for issue in response.data['results']]
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
