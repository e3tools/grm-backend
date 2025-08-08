import pytest
from django.test import override_settings
from parameterized import parameterized
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueStatusFactory,
    IssueTypeFactory,
    UserFactory
)
from issues.models import Issue


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class TestIssueCreateAPIView(APITestCase):
    """
    Test cases for the Issue creation API endpoint using Token Authentication.

    This test class covers various scenarios including successful creation,
    validation errors, authentication requirements, and edge cases.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
        "required_field": "This field is required.",
        "does_not_exist": "Invalid pk",
        "validation_failed": "Validation failed.",
        "creation_success": "Issue created successfully.",
    }

    def setUp(self):
        """Set up test data, user, token, and URL for each test."""
        self.url = reverse("issues:create-issue")

        # Create test user and token
        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)

        # Create test data using factories
        self.status = IssueStatusFactory()
        self.category = IssueCategoryFactory()
        self.issue_type = IssueTypeFactory()
        self.admin_region = AdministrativeRegionFactory()

    def authenticate_with_token(self):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_authentication_required_no_credentials(self):
        """Test that authentication is required when no credentials provided."""
        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        response = self.client.post(self.url, data, format='json')

        assert response.status_code == 401
        assert "detail" in response.data
        assert self.error_messages["authentication"] in str(response.data["detail"])

    def test_authentication_required_invalid_token(self):
        """Test authentication with invalid token."""
        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        self.client.credentials(HTTP_AUTHORIZATION='Token invalid_token_123')
        response = self.client.post(self.url, data, format='json')

        assert response.status_code == 401
        assert "detail" in response.data
        assert self.error_messages["invalid_token"] in str(response.data["detail"])

    def test_successful_issue_creation(self):
        """Test successful creation of an issue with valid data and token."""
        self.authenticate_with_token()

        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        response = self.client.post(self.url, data, format='json')
        response_data = response.data

        assert response.status_code == 201
        assert "message" in response_data
        assert "data" in response_data
        assert response_data["message"] == self.error_messages["creation_success"]
        assert Issue.objects.count() == 1

        # Verify the created issue data
        created_issue = response_data["data"]
        assert created_issue["status"]["id"] == self.status.id
        assert created_issue["category"]["id"] == self.category.id
        assert created_issue["issue_type"]["id"] == self.issue_type.id
        assert created_issue["administrative_region"]["id"] == self.admin_region.id
        assert "intake_date" in created_issue

    @parameterized.expand([
        ("status",),
        ("category",),
        ("issue_type",),
        ("administrative_region",),
    ])
    def test_missing_required_fields(self, missing_field):
        """Test validation error when required fields are missing."""
        self.authenticate_with_token()

        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        # Remove the specified field
        del data[missing_field]

        response = self.client.post(self.url, data, format='json')
        response_data = response.data

        assert response.status_code == 400
        assert "message" in response_data
        assert "errors" in response_data
        assert response_data["message"] == self.error_messages["validation_failed"]
        assert missing_field in response_data["errors"]
        assert self.error_messages["required_field"] in str(response_data["errors"][missing_field][0])

    @parameterized.expand([
        ("status", 99999),
        ("category", 99999),
        ("issue_type", 99999),
        ("administrative_region", 99999),
    ])
    def test_invalid_foreign_key_references(self, field_name, invalid_id):
        """Test validation error when providing invalid foreign key references."""
        self.authenticate_with_token()

        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        # Set invalid ID for the specified field
        data[field_name] = invalid_id

        response = self.client.post(self.url, data, format='json')
        response_data = response.data

        assert response.status_code == 400
        assert "message" in response_data
        assert "errors" in response_data
        assert response_data["message"] == self.error_messages["validation_failed"]
        assert field_name in response_data["errors"]

    def test_empty_payload(self):
        """Test validation error when providing empty payload."""
        self.authenticate_with_token()

        data = {}

        response = self.client.post(self.url, data, format='json')
        response_data = response.data

        assert response.status_code == 400
        assert "message" in response_data
        assert "errors" in response_data
        assert response_data["message"] == self.error_messages["validation_failed"]

        # All required fields should have errors
        required_fields = ['status', 'category', 'issue_type', 'administrative_region']
        for field in required_fields:
            assert field in response_data["errors"]

    def test_multiple_issues_creation(self):
        """Test creating multiple issues with the same data."""
        self.authenticate_with_token()

        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        # Create first issue
        response1 = self.client.post(self.url, data, format='json')
        assert response1.status_code == 201
        assert Issue.objects.count() == 1

        # Create second issue with same data (should be allowed)
        response2 = self.client.post(self.url, data, format='json')
        assert response2.status_code == 201
        assert Issue.objects.count() == 2

    def test_issue_creation_response_format(self):
        """Test that the response format matches expected structure."""
        self.authenticate_with_token()

        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        response = self.client.post(self.url, data, format='json')
        response_data = response.data

        assert response.status_code == 201

        # Verify response structure
        assert isinstance(response_data, dict)
        assert "message" in response_data
        assert "data" in response_data

        # Verify nested data structure
        issue_data = response_data["data"]
        assert "id" in issue_data
        assert "intake_date" in issue_data
        assert "status" in issue_data
        assert "category" in issue_data
        assert "issue_type" in issue_data
        assert "administrative_region" in issue_data

        # Verify nested objects have proper structure
        assert "name" in issue_data["status"]
        assert "name" in issue_data["category"]
        assert "name" in issue_data["issue_type"]

    def test_different_users_can_create_issues(self):
        """Test that different authenticated users can create issues."""
        # First user creates an issue
        self.authenticate_with_token()
        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        response1 = self.client.post(self.url, data, format='json')
        assert response1.status_code == 201
        assert Issue.objects.count() == 1

        # Second user creates an issue
        user2 = UserFactory()
        token2 = Token.objects.create(user=user2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token2.key}')

        response2 = self.client.post(self.url, data, format='json')
        assert response2.status_code == 201
        assert Issue.objects.count() == 2

    def test_token_authentication_headers(self):
        """Test different ways of providing token authentication."""
        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        # Test with proper Token format
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post(self.url, data, format='json')
        assert response.status_code == 201

        # Test with Bearer format (should fail with TokenAuthentication)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token.key}')
        response = self.client.post(self.url, data, format='json')
        assert response.status_code == 401

    def test_inactive_user_authentication(self):
        """Test that inactive users cannot authenticate."""
        # Create inactive user
        inactive_user = UserFactory(is_active=False)
        inactive_token = Token.objects.create(user=inactive_user)

        data = {
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.admin_region.id
        }

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {inactive_token.key}')
        response = self.client.post(self.url, data, format='json')

        assert response.status_code == 401
