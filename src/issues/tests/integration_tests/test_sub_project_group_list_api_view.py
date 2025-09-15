import pytest
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
from issues.factories import SubProjectGroupFactory
from issues.models import SubProjectGroup


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class SubProjectGroupListAPIViewTest(APITestCase):
    """
    Test cases for the SubProjectGroup list API endpoint using Token Authentication.

    This test class covers various scenarios including authentication,
    data retrieval, filtering, and response format validation.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
    }

    def setUp(self):
        """Set up test data, user, token, and URL for each test."""
        self.url = reverse("issues:list-subproject-groups")

        # Create test user and token
        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)

        # Create test subproject groups
        self.group = SubProjectGroupFactory()
        SubProjectGroupFactory()

    def authenticate_with_token(self):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_authentication_required_no_credentials(self):
        """Test that authentication is required when no credentials provided."""
        response = self.client.get(self.url)

        assert response.status_code == 401
        assert "detail" in response.data
        assert self.error_messages["authentication"] in str(response.data["detail"])

    def test_authentication_required_invalid_token(self):
        """Test authentication with invalid token."""
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid_token_123')
        response = self.client.get(self.url)

        assert response.status_code == 401
        assert "detail" in response.data
        assert self.error_messages["invalid_token"] in str(response.data["detail"])

    def test_successful_list_retrieval_paginated(self):
        """Test successful retrieval of paginated subproject groups list."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert isinstance(response_data, dict)

        # Check pagination structure
        assert 'count' in response_data
        assert 'next' in response_data
        assert 'previous' in response_data
        assert 'results' in response_data

        # Check data
        assert response_data['count'] == 2
        assert response_data['previous'] is None  # First page
        assert response_data['next'] is None  # Only one page needed
        assert isinstance(response_data['results'], list)
        assert len(response_data['results']) == 2

    def test_response_format_structure_paginated(self):
        """Test that the paginated response format matches expected structure."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert isinstance(response_data, dict)

        # Check pagination structure
        assert 'count' in response_data
        assert 'next' in response_data
        assert 'previous' in response_data
        assert 'results' in response_data

        assert isinstance(response_data['count'], int)
        assert response_data['next'] is None or isinstance(response_data['next'], str)
        assert response_data['previous'] is None or isinstance(response_data['previous'], str)
        assert isinstance(response_data['results'], list)
        assert len(response_data['results']) > 0

        # Check structure of first item in results
        first_item = response_data['results'][0]
        expected_fields = ['id', 'name']

        for field in expected_fields:
            assert field in first_item

        # Verify data types
        assert isinstance(first_item['id'], int)
        assert isinstance(first_item['name'], str)

    def test_empty_list_when_no_subprojects(self):
        """Test paginated response when no subproject groups exist."""
        # Delete all subproject groups
        SubProjectGroup.objects.all().delete()

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert isinstance(response_data, dict)
        assert response_data['count'] == 0
        assert response_data['next'] is None
        assert response_data['previous'] is None
        assert isinstance(response_data['results'], list)
        assert len(response_data['results']) == 0

    def test_single_subproject_response(self):
        """Test paginated response when only one subproject group exists."""
        # Delete all but one subproject group
        SubProjectGroup.objects.exclude(id=self.group.id).delete()

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert isinstance(response_data, dict)
        assert response_data['count'] == 1
        assert response_data['next'] is None
        assert response_data['previous'] is None
        assert len(response_data['results']) == 1
        assert response_data['results'][0]['name'] == self.group.name
        assert response_data['results'][0]['id'] == self.group.id

    def test_different_users_same_response(self):
        """Test that different authenticated users get the same paginated response."""
        # First user request
        self.authenticate_with_token()
        response1 = self.client.get(self.url)

        # Second user request
        user2 = UserFactory()
        token2 = Token.objects.create(user=user2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token2.key}')
        response2 = self.client.get(self.url)

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.data['count'] == response2.data['count']
        assert len(response1.data['results']) == len(response2.data['results'])

        # Responses should be identical (same data for all users)
        for i, item in enumerate(response1.data['results']):
            assert item == response2.data['results'][i]

    def test_inactive_user_authentication(self):
        """Test that inactive users cannot authenticate."""
        # Create inactive user
        inactive_user = UserFactory(is_active=False)
        inactive_token = Token.objects.create(user=inactive_user)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {inactive_token.key}')
        response = self.client.get(self.url)

        assert response.status_code == 401

    def test_large_dataset_performance(self):
        """Test paginated response with a larger dataset of subproject groups."""
        # Create many more subproject groups
        SubProjectGroupFactory.create_batch(50)

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert response_data['count'] == 52  # 2 original + 50 new
        assert len(response_data['results']) == 20  # Default page size

        # Should have next page
        assert response_data['next'] is not None
        assert response_data['previous'] is None  # First page

    def test_content_type_header(self):
        """Test that the response has correct content type."""
        self.authenticate_with_token()
        response = self.client.get(self.url)

        assert response.status_code == 200
        assert 'application/json' in response.get('Content-Type', '')

    def test_get_method_only_allowed(self):
        """Test that only GET method is allowed."""
        self.authenticate_with_token()

        # POST should not be allowed
        response_post = self.client.post(self.url, {})
        assert response_post.status_code == 405

        # PUT should not be allowed
        response_put = self.client.put(self.url, {})
        assert response_put.status_code == 405

        # DELETE should not be allowed
        response_delete = self.client.delete(self.url)
        assert response_delete.status_code == 405

        # PATCH should not be allowed
        response_patch = self.client.patch(self.url, {})
        assert response_patch.status_code == 405

        # GET should work
        response_get = self.client.get(self.url)
        assert response_get.status_code == 200
