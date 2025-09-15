import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.constants import (
    INACTIVE_USER_ERROR_MESSAGE,
    INVALID_INPUT_ERROR_MESSAGE,
    LOGIN_ERROR_MESSAGE,
    LOGIN_SUCCESS_MESSAGE,
)
from authentication.factories import UserFactory
from authentication.models import Citizen


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class CitizenLoginViewTest(APITestCase):
    """
    Test cases for the citizen authentication login API endpoint.

    This test class covers scenarios including successful login with a Citizen profile,
    login without a Citizen profile, invalid credentials, inactive users, and response
    format validation.
    """

    def setUp(self):
        """Set up test data and URL for each test."""
        self.url = reverse("authentication:citizen-login")

        # Create test user with known credentials
        self.username = "citizenuser"
        self.password = "citizenpassword123"
        self.user = UserFactory(username=self.username, password=self.password, is_active=True)
        # Attach Citizen profile to allow login
        self.citizen = Citizen.objects.create(user=self.user)

    def test_successful_login_with_citizen(self):
        """Test successful login when user has a Citizen profile."""
        login_data = {"username": self.username, "password": self.password}

        response = self.client.post(self.url, login_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

        # Check required fields in response
        required_fields = ["token", "user_id", "username", "message"]
        for field in required_fields:
            assert field in response.data

        # Verify response data
        assert response.data["user_id"] == self.user.id
        assert response.data["username"] == self.username
        assert response.data["message"] == LOGIN_SUCCESS_MESSAGE
        assert isinstance(response.data["token"], str)
        assert len(response.data["token"]) == 40  # Token length

        # Verify token was created in database
        token = Token.objects.get(user=self.user)
        assert token.key == response.data["token"]

    def test_login_without_citizen_profile(self):
        """Test login fails when user does not have a Citizen profile."""
        no_citizen_password = "password123"
        user_no_citizen = UserFactory(username="nocitizenuser", password=no_citizen_password, is_active=True)

        login_data = {"username": user_no_citizen.username, "password": no_citizen_password}
        response = self.client.post(self.url, login_data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["error"] == LOGIN_ERROR_MESSAGE

    def test_invalid_username(self):
        """Test login with invalid username."""
        login_data = {"username": "invaliduser", "password": self.password}

        response = self.client.post(self.url, login_data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["error"] == LOGIN_ERROR_MESSAGE

    def test_invalid_password(self):
        """Test login with invalid password."""
        login_data = {"username": self.username, "password": "wrongpassword"}

        response = self.client.post(self.url, login_data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["error"] == LOGIN_ERROR_MESSAGE

    def test_inactive_user(self):
        """Test login with inactive user account."""
        password = "password123"
        inactive_user = UserFactory(username="inactivecitizen", password=password, is_active=False)
        Citizen.objects.create(user=inactive_user)

        login_data = {"username": inactive_user.username, "password": password}
        response = self.client.post(self.url, login_data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == INACTIVE_USER_ERROR_MESSAGE

    def test_missing_username(self):
        """Test login with missing username field."""
        login_data = {"password": self.password}

        response = self.client.post(self.url, login_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == INVALID_INPUT_ERROR_MESSAGE
        assert "username" in response.data["details"]

    def test_missing_password(self):
        """Test login with missing password field."""
        login_data = {"username": self.username}

        response = self.client.post(self.url, login_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == INVALID_INPUT_ERROR_MESSAGE
        assert "password" in response.data["details"]

    def test_reuse_existing_token(self):
        """Test that existing token is reused for Citizen login."""
        existing_token = Token.objects.create(user=self.user)

        login_data = {"username": self.username, "password": self.password}
        response = self.client.post(self.url, login_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["token"] == existing_token.key
        assert Token.objects.filter(user=self.user).count() == 1
