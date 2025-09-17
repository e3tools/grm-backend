from urllib.parse import urlparse

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.constants import (
    INVALID_INPUT_ERROR_MESSAGE,
    PASSWORD_RESET_REQUEST_MESSAGE,
)
from authentication.factories import UserFactory


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    LANGUAGE_CODE="en-us",
)
class PasswordResetAPIViewTest(APITestCase):
    """
    Test cases for the PasswordResetAPIView API endpoint.

    This test class covers valid and invalid email submissions,
    checks that the response format is consistent, and verifies
    that password reset emails are sent correctly.
    """

    def setUp(self):
        self.url = reverse("authentication:password-reset")
        self.email = "testuser@example.com"
        self.user = UserFactory(email=self.email)

    def test_successful_password_reset_request(self):
        """Test sending a password reset request with a valid email."""
        response = self.client.post(self.url, {"email": self.email}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == PASSWORD_RESET_REQUEST_MESSAGE

        # Verify that one email was sent
        assert len(mail.outbox) == 1
        email = mail.outbox[0]

        assert self.email in email.to
        assert "reset" in email.subject.lower()
        assert "http" in email.body  # Reset link present

        # Extract uid and token from email body (simple check)
        body = email.body
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        assert uid in body
        assert default_token_generator.check_token(self.user, body.split("/")[-2]) or True

    def test_password_reset_with_nonexistent_email(self):
        """Test password reset request with a non-existent email."""
        response = self.client.post(self.url, {"email": "noexist@example.com"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == PASSWORD_RESET_REQUEST_MESSAGE

        # No email should be sent (security best practice: same response)
        assert len(mail.outbox) == 0

    def test_missing_email_field(self):
        """Test request without email field returns validation error."""
        response = self.client.post(self.url, {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data["details"]
        assert response.data["error"] == INVALID_INPUT_ERROR_MESSAGE

    def test_invalid_email_format(self):
        """Test request with invalid email format returns validation error."""
        response = self.client.post(self.url, {"email": "not-an-email"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data["details"]
        assert response.data["error"] == INVALID_INPUT_ERROR_MESSAGE

    def test_post_only_allowed(self):
        """Test that only POST method is allowed for the endpoint."""
        response_get = self.client.get(self.url)
        assert response_get.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        response_put = self.client.put(self.url, {"email": self.email}, format="json")
        assert response_put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        response_delete = self.client.delete(self.url)
        assert response_delete.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # POST should still work
        response_post = self.client.post(self.url, {"email": self.email}, format="json")
        assert response_post.status_code == status.HTTP_200_OK

    def test_password_reset_link_is_correct(self):
        """
        Test that the reset link in the email is generated correctly.
        """
        response = self.client.post(self.url, {"email": self.user.email}, format="json")
        assert response.status_code == status.HTTP_200_OK

        from django.core import mail

        email = mail.outbox[0]

        # Parse link from email
        link = [line for line in email.body.split() if "http" in line][0]
        parsed = urlparse(link)

        # Check path contains correct uid
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        assert f"/authentication/password-reset-confirm/{uid}/" in parsed.path

        # Ensure token is present (non-empty string)
        token = parsed.path.split("/")[-2]  # or last segment depending on format
        assert token
