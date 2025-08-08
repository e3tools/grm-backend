import pytest
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from issues.factories import IssueStatusFactory, UserFactory
from issues.models import IssueStatus


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class TestIssueStatusListAPIView(APITestCase):
    """
    Test cases for the IssueStatus list API endpoint using Token Authentication.

    This test class covers various scenarios including authentication,
    data retrieval, filtering, and response format validation.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
    }

    def setUp(self):
        """Set up test data, user, token, and URL for each test."""
        self.url = reverse("issues:list-issue-statuses")

        # Create test user and token
        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)

        # Create test issue statuses
        self.status_open = IssueStatusFactory(
            name="Open", final_status=False, initial_status=True, rejected_status=False, open_status=False
        )
        self.status_in_progress = IssueStatusFactory(
            name="In Progress", final_status=False, initial_status=False, rejected_status=False, open_status=True
        )
        self.status_closed = IssueStatusFactory(
            name="Closed", final_status=False, initial_status=False, rejected_status=True, open_status=False
        )
        self.status_rejected = IssueStatusFactory(
            name="Rejected", final_status=True, initial_status=False, rejected_status=False, open_status=False
        )

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
        """Test successful retrieval of paginated issue statuses list."""
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
        assert response_data['count'] == 4
        assert response_data['previous'] is None  # First page
        assert response_data['next'] is None  # Only one page needed
        assert isinstance(response_data['results'], list)
        assert len(response_data['results']) == 4

        # Verify ordering (alphabetical by name)
        status_names = [status['name'] for status in response_data['results']]
        expected_order = ["Closed", "In Progress", "Open", "Rejected"]
        assert status_names == expected_order

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
        first_status = response_data['results'][0]
        expected_fields = ['id', 'name', 'final_status', 'initial_status', 'rejected_status', 'open_status']

        for field in expected_fields:
            assert field in first_status

        # Verify data types
        assert isinstance(first_status['id'], int)
        assert isinstance(first_status['name'], str)
        assert isinstance(first_status['final_status'], bool)
        assert isinstance(first_status['initial_status'], bool)
        assert isinstance(first_status['rejected_status'], bool)
        assert isinstance(first_status['open_status'], bool)

    def test_specific_status_properties(self):
        """Test that specific status properties are correctly returned."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        # Find specific statuses and verify their properties
        statuses_by_name = {status['name']: status for status in response_data['results']}

        # Test Open status
        open_status = statuses_by_name['Open']
        assert open_status['final_status'] is False
        assert open_status['initial_status'] is True
        assert open_status['rejected_status'] is False
        assert open_status['open_status'] is False

        # Test Progress status
        in_progress_status = statuses_by_name['In Progress']
        assert in_progress_status['final_status'] is False
        assert in_progress_status['initial_status'] is False
        assert in_progress_status['rejected_status'] is False
        assert in_progress_status['open_status'] is True

        # Test Closed status
        closed_status = statuses_by_name['Closed']
        assert closed_status['final_status'] is False
        assert closed_status['initial_status'] is False
        assert closed_status['rejected_status'] is True
        assert closed_status['open_status'] is False

        # Test Rejected status
        rejected_status = statuses_by_name['Rejected']
        assert rejected_status['final_status'] is True
        assert rejected_status['initial_status'] is False
        assert rejected_status['rejected_status'] is False
        assert rejected_status['open_status'] is False

    def test_empty_list_when_no_statuses(self):
        """Test paginated response when no issue statuses exist."""
        # Delete all statuses
        IssueStatus.objects.all().delete()

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

    def test_single_status_response(self):
        """Test paginated response when only one status exists."""
        # Delete all but one status
        IssueStatus.objects.exclude(id=self.status_open.id).delete()

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert isinstance(response_data, dict)
        assert response_data['count'] == 1
        assert response_data['next'] is None
        assert response_data['previous'] is None
        assert len(response_data['results']) == 1
        assert response_data['results'][0]['name'] == self.status_open.name
        assert response_data['results'][0]['id'] == self.status_open.id

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
        for i, status in enumerate(response1.data['results']):
            assert status['id'] == response2.data['results'][i]['id']
            assert status['name'] == response2.data['results'][i]['name']

    def test_inactive_user_authentication(self):
        """Test that inactive users cannot authenticate."""
        # Create inactive user
        inactive_user = UserFactory(is_active=False)
        inactive_token = Token.objects.create(user=inactive_user)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {inactive_token.key}')
        response = self.client.get(self.url)

        assert response.status_code == 401

    def test_large_dataset_performance(self):
        """Test paginated response with a larger dataset of statuses."""
        # Create many more statuses
        IssueStatusFactory.create_batch(50)

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert response_data['count'] == 54  # 4 original + 50 new
        assert len(response_data['results']) == 20  # Default page size

        # Should have next page
        assert response_data['next'] is not None
        assert response_data['previous'] is None  # First page

        # Verify they're still properly ordered
        status_names = [status['name'] for status in response_data['results']]
        assert status_names == sorted(status_names)

    def test_status_ordering_case_insensitive(self):
        """Test that status ordering is case-insensitive in paginated response."""
        # Create statuses with different cases
        IssueStatusFactory(name="Apple")
        IssueStatusFactory(name="Banana")
        IssueStatusFactory(name="Cherry")
        IssueStatusFactory(name="Date")

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200

        # Extract names and verify alphabetical ordering
        status_names = [status['name'] for status in response_data['results']]

        # Should be ordered alphabetically regardless of case
        expected_start = ["Apple", "Banana", "Cherry", "Closed", "Date"]
        actual_start = status_names[:5]
        assert actual_start == expected_start

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
