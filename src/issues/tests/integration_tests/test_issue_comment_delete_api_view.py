from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
from grm.constants import COMMENT_DELETE_ERROR_MESSAGE, NOT_FOUND_MESSAGE
from grm.utils import reset_sequences
from issues.factories import CommentFactory, IssueFactory
from issues.models import Comment


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class IssueCommentDeleteAPIViewTest(APITestCase):
    """Integration tests for the IssueCommentDeleteAPIView."""

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

        # Issue and comment
        self.issue = IssueFactory(reporter=self.reporter_user, assignee=self.assignee_user)
        self.comment = CommentFactory(issue=self.issue, user=self.reporter_user, comment="Initial comment")

        self.url = reverse("issues:delete-issue-comment", kwargs={"id": self.comment.id})

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_reporter_can_delete_comment(self):
        before = timezone.now()
        self.authenticate(self.reporter_token)
        response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Comment.objects.filter(id=self.comment.id).exists()

        # Check last_activity was updated
        self.reporter_user.refresh_from_db()
        assert self.reporter_user.last_activity >= before

    def test_assignee_can_delete_own_comment(self):
        assignee_comment = CommentFactory(issue=self.issue, user=self.assignee_user, comment="By assignee")
        url = reverse("issues:delete-issue-comment", kwargs={"id": assignee_comment.id})

        self.authenticate(self.assignee_token)
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Comment.objects.filter(id=assignee_comment.id).exists()

    def test_other_user_cannot_delete_comment(self):
        self.authenticate(self.other_token)
        response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Comment.objects.filter(id=self.comment.id).exists()

    def test_authentication_required(self):
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert Comment.objects.filter(id=self.comment.id).exists()

    def test_nonexistent_comment_returns_404(self):
        self.authenticate(self.reporter_token)
        url = reverse("issues:delete-issue-comment", kwargs={"id": 9999})
        response = self.client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        self.assertEqual(response.data['detail'], NOT_FOUND_MESSAGE)

    def test_delete_comment_as_unrelated_user(self):
        """Users who are not reporter or assignee cannot delete comments."""

        self.authenticate(self.other_token)
        response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Comment.objects.filter(id=self.comment.id).exists()

    def test_internal_server_error(self):
        """Simulate an unexpected exception inside the view."""
        self.authenticate(self.reporter_token)
        with patch("issues.views.IssueCommentDeleteAPIView.perform_destroy", side_effect=RuntimeError("boom")):
            response = self.client.delete(self.url)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['detail'] == COMMENT_DELETE_ERROR_MESSAGE

    def test_delete_method_only_allowed(self):
        """Ensure only DELETE is permitted."""
        self.authenticate(self.reporter_token)
        assert self.client.post(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert self.client.put(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert self.client.patch(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert self.client.get(self.url).status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_idempotent_delete_returns_404_on_second_comment(self):
        """Attempting to delete already deleted comment returns 404."""
        self.authenticate(self.reporter_token)

        # First delete succeeds
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Second delete returns 404
        response = self.client.delete(self.url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
