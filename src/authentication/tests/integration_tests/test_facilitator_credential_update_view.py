from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

ENDPOINT = reverse("facilitator-login")  # name registered in urls.py


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def facilitator_user(db):
    user = User.objects.create_user(
        username="facilitator@example.com",
        email="facilitator@example.com",
        password="OldPassword1!",
        is_active=True,
    )

    user.last_login = None
    user.save(update_fields=["last_login"])

    from authentication.models import Facilitator  # noqa: PLC0415

    Facilitator.objects.create(user=user)

    return user


VALID_CODE = "123456"
VALID_PAYLOAD = {
    "username": "facilitator@example.com",
    "password": "NewSecurePassword1!",
    "code": VALID_CODE,
}


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


class TestFacilitatorCredentialUpdateSuccess:
    @patch("authentication.views.get_validation_code", return_value=VALID_CODE)
    def test_returns_200_with_token(self, mock_code, api_client, facilitator_user):
        response = api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        assert response.status_code == status.HTTP_200_OK

    @patch("authentication.views.get_validation_code", return_value=VALID_CODE)
    def test_response_body_contains_expected_fields(self, mock_code, api_client, facilitator_user):
        response = api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        data = response.json()
        assert "token" in data
        assert "user_id" in data
        assert "username" in data
        assert "message" in data

    @patch("authentication.views.get_validation_code", return_value=VALID_CODE)
    def test_response_username_matches_input(self, mock_code, api_client, facilitator_user):
        response = api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        assert response.json()["username"] == facilitator_user.username

    @patch("authentication.views.get_validation_code", return_value=VALID_CODE)
    def test_last_login_is_set_after_successful_call(self, mock_code, api_client, facilitator_user):
        assert facilitator_user.last_login is None

        api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        facilitator_user.refresh_from_db()
        assert facilitator_user.last_login is not None

    @patch("authentication.views.get_validation_code", return_value=VALID_CODE)
    def test_token_is_created_for_user(self, mock_code, api_client, facilitator_user):
        from rest_framework.authtoken.models import Token  # noqa: PLC0415

        api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        assert Token.objects.filter(user=facilitator_user).exists()

    @patch("authentication.views.get_validation_code", return_value=VALID_CODE)
    def test_no_authentication_header_required(self, mock_code, api_client, facilitator_user):
        """Endpoint must be accessible without any auth token."""
        # api_client has no credentials set by default
        response = api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# User not found
# ---------------------------------------------------------------------------


class TestFacilitatorCredentialUpdateUserNotFound:
    def test_unknown_username_returns_401(self, api_client, db):
        payload = {**VALID_PAYLOAD, "username": "nobody@example.com"}
        response = api_client.post(ENDPOINT, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unknown_username_returns_error_key(self, api_client, db):
        payload = {**VALID_PAYLOAD, "username": "nobody@example.com"}
        response = api_client.post(ENDPOINT, payload, format="json")

        assert "error" in response.json()


# ---------------------------------------------------------------------------
# Inactive user
# ---------------------------------------------------------------------------


class TestFacilitatorCredentialUpdateInactiveUser:
    def test_inactive_user_returns_403(self, api_client, facilitator_user):
        facilitator_user.is_active = False
        facilitator_user.save(update_fields=["is_active"])

        response = api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_inactive_user_returns_error_key(self, api_client, facilitator_user):
        facilitator_user.is_active = False
        facilitator_user.save(update_fields=["is_active"])

        response = api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        assert "error" in response.json()


# ---------------------------------------------------------------------------
# Non-facilitator user (no facilitator profile)
# ---------------------------------------------------------------------------


class TestFacilitatorCredentialUpdateNoFacilitatorProfile:
    def test_user_without_facilitator_returns_401(self, api_client, db):
        user = User.objects.create_user(
            username="citizen@example.com",
            email="citizen@example.com",
            password="SomePassword1!",
            is_active=True,
        )
        user.last_login = None
        user.save(update_fields=["last_login"])

        payload = {**VALID_PAYLOAD, "username": "citizen@example.com"}
        response = api_client.post(ENDPOINT, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Already logged in (last_login is not None)
# ---------------------------------------------------------------------------


class TestFacilitatorCredentialUpdateAlreadyRegistered:
    @patch("authentication.views.get_validation_code", return_value=VALID_CODE)
    def test_already_logged_in_user_returns_401(self, mock_code, api_client, facilitator_user):
        from django.utils import timezone  # noqa: PLC0415

        facilitator_user.last_login = timezone.now()
        facilitator_user.save(update_fields=["last_login"])

        response = api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("authentication.views.get_validation_code", return_value=VALID_CODE)
    def test_already_logged_in_returns_error_message(self, mock_code, api_client, facilitator_user):
        from django.utils import timezone  # noqa: PLC0415

        facilitator_user.last_login = timezone.now()
        facilitator_user.save(update_fields=["last_login"])

        response = api_client.post(ENDPOINT, VALID_PAYLOAD, format="json")

        assert "error" in response.json()


# ---------------------------------------------------------------------------
# Invalid / wrong code
# ---------------------------------------------------------------------------


class TestFacilitatorCredentialUpdateInvalidCode:
    @patch("authentication.views.get_validation_code", return_value="999999")
    def test_wrong_code_returns_401(self, mock_code, api_client, facilitator_user):
        payload = {**VALID_PAYLOAD, "code": "000000"}
        response = api_client.post(ENDPOINT, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("authentication.views.get_validation_code", return_value="999999")
    def test_wrong_code_returns_error_key(self, mock_code, api_client, facilitator_user):
        payload = {**VALID_PAYLOAD, "code": "000000"}
        response = api_client.post(ENDPOINT, payload, format="json")

        assert "error" in response.json()

    @patch("authentication.views.get_validation_code", return_value="999999")
    def test_wrong_code_does_not_update_last_login(self, mock_code, api_client, facilitator_user):
        payload = {**VALID_PAYLOAD, "code": "000000"}
        api_client.post(ENDPOINT, payload, format="json")

        facilitator_user.refresh_from_db()
        assert facilitator_user.last_login is None
