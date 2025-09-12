from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.models import Citizen, User
from grm.constants import (
    CITIZEN_SUCCESS_MESSAGE,
    EMAIL_ERROR_MESSAGE,
    USERNAME_ERROR_MESSAGE,
)


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class CitizenRegistrationCreateAPIViewTest(APITestCase):
    """
    Test cases for the citizen registration API endpoint.

    This test class covers various scenarios including successful registration,
    validation errors, duplicate emails, and response format validation.
    """

    def setUp(self):
        """Set up test data and URL for each test."""
        self.url = reverse("authentication:citizen-register")

        self.valid_registration_data = {
            'username': 'john.doe',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
        }

    def test_successful_registration(self):
        """Test successful citizen registration with valid data."""
        response = self.client.post(self.url, self.valid_registration_data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert isinstance(response.data, dict)

        # Check required fields in response
        required_fields = ['message', 'data']
        for field in required_fields:
            assert field in response.data

        # Check data structure
        data = response.data['data']
        expected_data_fields = ['id', 'username', 'email', 'first_name', 'last_name']
        for field in expected_data_fields:
            assert field in data

        # Verify response data
        assert data['username'] == 'john.doe'
        assert data['email'] == 'john.doe@example.com'
        assert data['first_name'] == 'John'
        assert data['last_name'] == 'Doe'
        assert response.data['message'] == CITIZEN_SUCCESS_MESSAGE

        # Verify user was created in database
        user = User.objects.get(username='john.doe', email='john.doe@example.com')
        assert user.first_name == 'John'
        assert user.last_name == 'Doe'
        assert user.check_password('SecurePassword123!')

        # Verify citizen was created
        citizen = Citizen.objects.get(user=user)
        assert citizen.user == user

    def test_duplicate_username_validation(self):
        """Test registration with duplicate username."""
        User.objects.create_user(
            email='new.email@example.com',
            username='john.doe',
            password='password123',
            first_name='Existing',
            last_name='User',
        )

        response = self.client.post(self.url, self.valid_registration_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.assertEqual(str(response.data['errors']['username'][0]), USERNAME_ERROR_MESSAGE)

    def test_duplicate_email_validation(self):
        """Test registration with duplicate email address."""
        User.objects.create_user(
            email='john.doe@example.com',
            username='new.username',
            password='password123',
            first_name='Existing',
            last_name='User',
        )

        response = self.client.post(self.url, self.valid_registration_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.assertEqual(str(response.data['errors']['email'][0]), EMAIL_ERROR_MESSAGE)

    def test_password_confirmation_mismatch(self):
        """Test registration with mismatched password confirmation."""
        invalid_data = self.valid_registration_data.copy()
        invalid_data['confirm_password'] = 'DifferentPassword123!'

        response = self.client.post(self.url, invalid_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data
        assert 'confirm_password' in response.data['errors']
        assert 'Password confirmation does not match.' in response.data['errors']['confirm_password'][0]

    def test_missing_required_fields(self):
        """Test registration with missing required fields."""
        required_fields = ['username', 'first_name', 'last_name', 'email', 'password', 'confirm_password']

        for field in required_fields:
            incomplete_data = self.valid_registration_data.copy()
            del incomplete_data[field]

            response = self.client.post(self.url, incomplete_data, format='json')

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert 'errors' in response.data
            assert field in response.data['errors']

    def test_empty_field_validation(self):
        """Test registration with empty fields."""
        empty_data = {
            'username': '',
            'first_name': '',
            'last_name': '',
            'email': '',
            'password': '',
            'confirm_password': '',
        }

        response = self.client.post(self.url, empty_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data

        # All fields should have validation errors
        expected_fields = ['username', 'first_name', 'last_name', 'email', 'password', 'confirm_password']
        for field in expected_fields:
            assert field in response.data['errors']

    def test_invalid_username_format(self):
        """Test registration with invalid username format."""
        invalid_data = self.valid_registration_data.copy()
        invalid_data['username'] = 'invalid-username-format!'

        response = self.client.post(self.url, invalid_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data
        assert 'username' in response.data['errors']

    def test_invalid_email_format(self):
        """Test registration with invalid email format."""
        invalid_data = self.valid_registration_data.copy()
        invalid_data['email'] = 'invalid-email-format'

        response = self.client.post(self.url, invalid_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data
        assert 'email' in response.data['errors']

    def test_weak_password_validation(self):
        """Test registration with weak password based on configured validators."""
        # Test minimum length validator (min_length=8)
        short_password_data = self.valid_registration_data.copy()
        short_password_data['password'] = '1234567'  # 7 characters, below minimum
        short_password_data['confirm_password'] = '1234567'

        response = self.client.post(self.url, short_password_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data
        assert 'password' in response.data['errors']
        assert any('at least 8 characters' in str(error) for error in response.data['errors']['password'])

    def test_numeric_password_validation(self):
        """Test registration with numeric-only password."""
        # Test numeric password validator
        numeric_password_data = self.valid_registration_data.copy()
        numeric_password_data['password'] = '12345678'  # 8 characters but all numeric
        numeric_password_data['confirm_password'] = '12345678'

        response = self.client.post(self.url, numeric_password_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data
        assert 'password' in response.data['errors']
        assert any('entirely numeric' in str(error) for error in response.data['errors']['password'])

    def test_valid_password_passes_validation(self):
        """Test that a valid password passes all validators."""
        valid_password_data = self.valid_registration_data.copy()
        valid_password_data['password'] = 'ValidPass123'  # 12 characters, mixed alphanumeric
        valid_password_data['confirm_password'] = 'ValidPass123'
        valid_password_data['email'] = 'valid.test@example.com'

        response = self.client.post(self.url, valid_password_data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert 'message' in response.data
        assert response.data['message'] == CITIZEN_SUCCESS_MESSAGE

    def test_whitespace_trimming(self):
        """Test that whitespace is properly handled in names."""
        data_with_spaces = self.valid_registration_data.copy()
        data_with_spaces['username'] = '  john.doe  '
        data_with_spaces['first_name'] = '  John  '
        data_with_spaces['last_name'] = '  Doe  '
        data_with_spaces['email'] = '  john.doe@example.com  '

        response = self.client.post(self.url, data_with_spaces, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        # Verify trimmed values in database
        user = User.objects.get(username="john.doe", email='john.doe@example.com')
        assert user.first_name == 'John'
        assert user.last_name == 'Doe'

    def test_case_sensitive_username(self):
        """Test that username comparison is case-insensitive."""
        # Register with lowercase email
        response1 = self.client.post(self.url, self.valid_registration_data, format='json')
        assert response1.status_code == status.HTTP_201_CREATED

        # Try to register with uppercase version of same username
        duplicate_data = self.valid_registration_data.copy()
        duplicate_data['username'] = 'JOHN.DOE'

        response2 = self.client.post(self.url, duplicate_data, format='json')
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        self.assertEqual(str(response2.data['errors']['username'][0]), USERNAME_ERROR_MESSAGE)

    def test_case_sensitive_email(self):
        """Test that email comparison is case-insensitive."""
        # Register with lowercase email
        response1 = self.client.post(self.url, self.valid_registration_data, format='json')
        assert response1.status_code == status.HTTP_201_CREATED

        # Try to register with uppercase version of same email
        duplicate_data = self.valid_registration_data.copy()
        duplicate_data['username'] = 'new_username'
        duplicate_data['email'] = 'JOHN.DOE@EXAMPLE.COM'

        response2 = self.client.post(self.url, duplicate_data, format='json')
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response2.data['errors']
        assert 'user with this email address already exists.' in response2.data['errors']['email'][0]

    def test_long_field_values(self):
        """Test registration with very long field values."""
        long_data = self.valid_registration_data.copy()
        long_data['username'] = 'u' * 151  # Longer than typical max_length
        long_data['first_name'] = 'f' * 151
        long_data['last_name'] = 'l' * 151

        response = self.client.post(self.url, long_data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        expected_fields = ['username', 'first_name', 'last_name']
        for field in expected_fields:
            assert field in response.data['errors']

    def test_unicode_characters_in_names(self):
        """Test registration with Unicode characters in names."""
        unicode_data = self.valid_registration_data.copy()
        unicode_data['first_name'] = 'José'
        unicode_data['last_name'] = 'María'
        unicode_data['email'] = 'jose.maria@example.com'

        response = self.client.post(self.url, unicode_data, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email='jose.maria@example.com')
        assert user.first_name == 'José'
        assert user.last_name == 'María'

    def test_internal_server_error(self):
        """Test internal server error response."""
        with patch(
            "authentication.views.CitizenRegistrationCreateAPIView.get_serializer",
            side_effect=RuntimeError("Database error"),
        ):
            response = self.client.post(self.url, self.valid_registration_data, format='json')

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['message'] == 'An error occurred while registering the citizen.'

    def test_post_method_only(self):
        """Test that only POST method is allowed."""
        # GET should not be allowed
        response_get = self.client.get(self.url)
        assert response_get.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # PUT should not be allowed
        response_put = self.client.put(self.url, self.valid_registration_data, format='json')
        assert response_put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # DELETE should not be allowed
        response_delete = self.client.delete(self.url)
        assert response_delete.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # PATCH should not be allowed
        response_patch = self.client.patch(self.url, self.valid_registration_data, format='json')
        assert response_patch.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # POST should work
        response_post = self.client.post(self.url, self.valid_registration_data, format='json')
        assert response_post.status_code == status.HTTP_201_CREATED

    def test_content_type_header(self):
        """Test that the response has correct content type."""
        response = self.client.post(self.url, self.valid_registration_data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert 'application/json' in response.get('Content-Type', '')

    def test_response_format_consistency(self):
        """Test that response format is consistent across different scenarios."""
        # Test successful registration format
        response = self.client.post(self.url, self.valid_registration_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert isinstance(response.data, dict)
        assert 'message' in response.data
        assert 'data' in response.data

        # Test error format
        invalid_data = {'email': 'invalid'}
        error_response = self.client.post(self.url, invalid_data, format='json')
        assert error_response.status_code == status.HTTP_400_BAD_REQUEST
        assert isinstance(error_response.data, dict)
        assert 'message' in error_response.data
        assert 'errors' in error_response.data

    def test_no_authentication_required(self):
        """Test that no authentication is required for registration."""
        # Should work without any authentication headers
        response = self.client.post(self.url, self.valid_registration_data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_citizen_user_relationship(self):
        """Test that Citizen is properly linked to User."""
        response = self.client.post(self.url, self.valid_registration_data, format='json')

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email='john.doe@example.com')
        citizen = Citizen.objects.get(user=user)

        # Test relationship
        assert citizen.user == user
        assert hasattr(user, 'citizen')
        assert user.citizen == citizen

        # Test citizen name property
        assert citizen.name == 'John Doe'
