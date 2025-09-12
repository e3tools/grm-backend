from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from grm.constants import ISSUE_RETRIEVE_ERROR_MESSAGE
from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueFactory,
    IssueStatusFactory,
    IssueTypeFactory,
    UserFactory,
)


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class IssueRetrieveAPIViewTest(APITestCase):
    """
    Test cases for the Issue list API endpoint using Token Authentication.

    This test class covers various scenarios including authentication,
    data retrieval, pagination, and response format validation.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
    }

    def setUp(self):
        """Set up test data, user, token, and URL for each test."""

        reset_sequences()

        # Create test users
        self.reporter_user = UserFactory()
        self.assignee_user = UserFactory()
        self.other_user = UserFactory()

        # Create tokens
        self.reporter_token = Token.objects.create(user=self.reporter_user)
        self.assignee_token = Token.objects.create(user=self.assignee_user)
        self.other_token = Token.objects.create(user=self.other_user)

        # Create required objects
        self.status_open = IssueStatusFactory(name="Open")
        self.category_env = IssueCategoryFactory(name="Environmental")
        self.issue_type_complaint = IssueTypeFactory(name="Complaint")
        self.admin_region = AdministrativeRegionFactory(name="KADJÈRÈ")

        self.issue = IssueFactory(
            description='Test description',
            administrative_region=self.admin_region,
            reporter=self.reporter_user,
            assignee=self.assignee_user,
            category=self.category_env,
            issue_type=self.issue_type_complaint,
            status=self.status_open,
            tracking_code='TEST-001',
        )

        self.url = reverse("issues:issue-detail", kwargs={"id": self.issue.id})

    def authenticate_with_token(self):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.reporter_token.key}')

    def test_authentication_required_no_credentials(self):
        """Test that authentication is required when no credentials provided."""
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data
        assert self.error_messages["authentication"] in str(response.data["detail"])

    def test_authentication_required_invalid_token(self):
        """Test authentication with invalid token."""
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid_token_123')
        response = self.client.get(self.url)

        assert response.status_code == 401
        assert "detail" in response.data
        assert self.error_messages["invalid_token"] in str(response.data["detail"])

    def test_issue_response_format_structure(self):
        """Test that the issue response format matches expected structure."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert isinstance(response_data, dict)

        # Check structure of first item in results
        first_issue = response_data
        expected_fields = [
            'id',
            'tracking_code',
            'intake_date',
            'status',
            'category',
            'issue_type',
            'administrative_region',
            'reporter',
            'assignee',
        ]

        for field in expected_fields:
            assert field in first_issue

        # Verify basic data types
        assert isinstance(first_issue['id'], int)
        assert isinstance(first_issue['tracking_code'], str)
        assert isinstance(first_issue['intake_date'], str)  # DRF DateTimeField is serialized as string

        # Check related object structures
        related_fields = ['status', 'category', 'issue_type', 'reporter', 'assignee']
        for field in related_fields:
            assert isinstance(first_issue[field], dict)
            assert 'id' in first_issue[field]
            assert isinstance(first_issue[field]['id'], int)

        assert isinstance(first_issue['administrative_region'], dict)
        assert 'administrative_id' in first_issue['administrative_region']
        assert isinstance(first_issue['administrative_region']['administrative_id'], str)

    def test_issue_foreign_key_serialization_structure(self):
        """Test that all FK fields in Issue are properly serialized with correct structure."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        network_issue = response.data

        assert response.status_code == 200
        assert network_issue is not None

        # Test status structure
        issue_status = network_issue['status']
        assert issue_status['id'] == self.status_open.id
        assert issue_status['name'] == self.status_open.name
        assert issue_status['final_status'] == self.status_open.final_status
        assert issue_status['initial_status'] == self.status_open.initial_status
        assert issue_status['rejected_status'] == self.status_open.rejected_status
        assert issue_status['open_status'] == self.status_open.open_status

        # Test category structure
        category = network_issue['category']
        assert category['id'] == self.category_env.id
        assert category['name'] == self.category_env.name

        # Test issue_type structure
        issue_type = network_issue['issue_type']
        assert issue_type['id'] == self.issue_type_complaint.id
        assert issue_type['name'] == self.issue_type_complaint.name

        # Test administrative_region structure
        admin_region = network_issue['administrative_region']
        assert admin_region['administrative_id'] == str(self.admin_region.id)
        assert admin_region['name'] == self.admin_region.name

        # Test reporter structure
        reporter = network_issue['reporter']
        assert reporter['id'] == self.reporter_user.id
        assert reporter['name'] == self.reporter_user.name

        # Test assignee structure
        assignee = network_issue['assignee']
        assert assignee['id'] == self.assignee_user.id
        assert assignee['name'] == self.assignee_user.name

    def test_different_users_same_response(self):
        """Test that different authenticated users get the same response."""
        # First user request
        self.authenticate_with_token()
        response1 = self.client.get(self.url)

        # Second user request
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')
        response2 = self.client.get(self.url)

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert len(response1.data.keys()) == len(response2.data.keys())

        # Responses should be identical
        assert response1.data['id'] == response2.data['id']
        assert response1.data['tracking_code'] == response2.data['tracking_code']
        assert response1.data['intake_date'] == response2.data['intake_date']
        assert response1.data['status'] == response2.data['status']
        assert response1.data['category'] == response2.data['category']
        assert response1.data['issue_type'] == response2.data['issue_type']
        assert response1.data['administrative_region'] == response2.data['administrative_region']
        assert response1.data['reporter'] == response2.data['reporter']
        assert response1.data['assignee'] == response2.data['assignee']

    def test_inactive_user_authentication(self):
        """Test that inactive users cannot authenticate."""
        # Change reporter user to inactive user
        inactive_user = self.reporter_user
        inactive_user.is_active = False
        inactive_user.save()

        self.authenticate_with_token()
        response = self.client.get(self.url)

        assert response.status_code == 401

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

    def test_complete_issue_data_integrity(self):
        """Test that all issue data is correctly serialized and maintains integrity."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        issue_result = response.data

        assert response.status_code == 200
        assert issue_result is not None

        # Verify main fields
        assert issue_result['id'] == self.issue.id
        assert issue_result['tracking_code'] == "TEST-001"
        # intake_date serialized as ISO format string
        assert issue_result['intake_date'] == self.issue.intake_date.isoformat().replace('+00:00', 'Z')

        # Verify foreign key structures
        assert issue_result['status']['id'] == self.issue.status.id
        assert issue_result['status']['name'] == "Open"

        assert issue_result['category']['id'] == self.issue.category.id
        assert issue_result['category']['name'] == "Environmental"

        assert issue_result['issue_type']['id'] == self.issue.issue_type.id
        assert issue_result['issue_type']['name'] == "Complaint"

        assert issue_result['administrative_region']['administrative_id'] == str(self.issue.administrative_region.id)
        assert issue_result['administrative_region']['name'] == "KADJÈRÈ"

        assert issue_result['reporter']['id'] == self.issue.reporter.id
        assert issue_result['reporter']['name'] == self.reporter_user.name

        assert issue_result['assignee']['id'] == self.issue.assignee.id
        assert issue_result['assignee']['name'] == self.assignee_user.name

    def test_assignee_can_retrieve_issue(self):
        """Test that the assignee can retrieve the issue."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.assignee_token.key}')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.issue.id)

    def test_other_user_cannot_retrieve_issue(self):
        """Test that other users cannot retrieve the issue."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nonexistent_issue_returns_404(self):
        """Test that requesting a non-existent issue returns 404."""
        self.authenticate_with_token()

        url = reverse("issues:issue-detail", kwargs={"id": 9999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_internal_server_error(self):
        """Test internal server error response."""

        self.authenticate_with_token()
        with patch("issues.views.IssueRetrieveAPIView.get_object", side_effect=RuntimeError("boom")):
            response = self.client.get(self.url)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['detail'] == ISSUE_RETRIEVE_ERROR_MESSAGE
