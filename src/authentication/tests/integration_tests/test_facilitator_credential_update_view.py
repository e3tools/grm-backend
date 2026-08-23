from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.constants import (
    INACTIVE_USER_ERROR_MESSAGE,
    LOGIN_ERROR_MESSAGE,
    LOGIN_SUCCESS_MESSAGE,
)
from authentication.factories import FacilitatorFactory, UserFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class FacilitatorCredentialUpdateAPIViewTest(APITestCase):
    """Test the FacilitatorCredentialUpdateAPIView."""

    def setUp(self):
        """Set up test data and URL for each test."""
        self.url = reverse("authentication:facilitator-login")
        self.facilitator = FacilitatorFactory(user__last_login=None)
        self.user = self.facilitator.user
        self.valid_code = "123456"
        self.valid_payload = {
            "username": self.user.username,
            "password": "NewSecurePassword1!",
            "code": self.valid_code,
        }

    @patch("authentication.views.get_validation_code")
    def test_successful_credential_update(self, mock_get_code):
        """Valid code and password should update credentials and return token."""
        mock_get_code.return_value = self.valid_code

        response = self.client.post(self.url, self.valid_payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "token" in data
        assert data["user_id"] == self.user.id
        assert data["username"] == self.user.username
        assert data["message"] == LOGIN_SUCCESS_MESSAGE

        # Verify database changes
        self.user.refresh_from_db()
        assert self.user.last_login is not None
        assert self.user.check_password("NewSecurePassword1!")
        assert Token.objects.filter(user=self.user).exists()

    def test_user_not_found(self):
        """Unknown username should return 401."""
        payload = {**self.valid_payload, "username": "nobody@example.com"}
        response = self.client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"] == LOGIN_ERROR_MESSAGE

    def test_inactive_user(self):
        """Inactive user should return 403."""
        self.user.is_active = False
        self.user.save()

        response = self.client.post(self.url, self.valid_payload, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"] == INACTIVE_USER_ERROR_MESSAGE

    def test_non_facilitator_user(self):
        """User without facilitator profile should return 401."""
        user = UserFactory(last_login=None)
        payload = {**self.valid_payload, "username": user.username}
        response = self.client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"] == "Incorrect authentication credentials."

    def test_already_registered_user(self):
        """A facilitator who already logged in cannot use this endpoint."""
        self.user.last_login = timezone.now()
        self.user.save()

        response = self.client.post(self.url, self.valid_payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"] == "User already registered."

    @patch("authentication.views.get_validation_code")
    def test_invalid_code(self, mock_get_code):
        """Wrong code should return 401 and not update last_login."""
        mock_get_code.return_value = "999999"
        payload = {**self.valid_payload, "code": "000000"}

        response = self.client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error"] == "Incorrect authentication credentials."

        self.user.refresh_from_db()
        assert self.user.last_login is None

    @patch("authentication.views.get_validation_code")
    def test_no_authentication_header_required(self, mock_get_code):
        """Endpoint must be accessible without any auth token."""
        mock_get_code.return_value = self.valid_code
        # client in APITestCase has no credentials by default
        response = self.client.post(self.url, self.valid_payload, format="json")

        assert response.status_code == status.HTTP_200_OK
