import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeRegionFactory,
    CitizenAgeGroupFactory,
    CitizenFactory,
    CitizenGroupFactory,
    IssueCategoryFactory,
    IssueFactory,
    IssueStatusFactory,
    IssueTypeFactory,
    UserFactory,
)
from issues.models import Issue


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class IssueListAPIViewTest(APITestCase):
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
        self.url = reverse("issues:list-issues")

        reset_sequences()

        # Create test user and token
        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)

        # Related objects
        self.status_open = IssueStatusFactory(name="Open")
        self.category_env = IssueCategoryFactory(name="Environmental")
        self.issue_type_complaint = IssueTypeFactory(name="Complaint")
        self.admin_region = AdministrativeRegionFactory(name="KADJÈRÈ")
        self.citizen_age_group = CitizenAgeGroupFactory()
        self.citizen_group = CitizenGroupFactory(name="group", type="citizen_group")
        self.citizen_group_2 = CitizenGroupFactory(name="group2", type="citizen_group_2")
        self.citizen = CitizenFactory(
            age_group=self.citizen_age_group, group=self.citizen_group, group_2=self.citizen_group_2
        )

        # Create issues
        self.issue1 = IssueFactory(
            status=self.status_open,
            category=self.category_env,
            issue_type=self.issue_type_complaint,
            administrative_region=self.admin_region,
            reporter=self.user,
            assignee=self.user,
            citizen=self.citizen,
            description="Network connectivity issue",
        )
        self.issue2 = IssueFactory(
            status=self.status_open,
            category=self.category_env,
            issue_type=self.issue_type_complaint,
            administrative_region=self.admin_region,
            reporter=self.user,
            assignee=self.user,
            citizen=self.citizen,
            description="Water pollution complaint",
        )

    def authenticate_with_token(self):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

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

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data
        assert self.error_messages["invalid_token"] in str(response.data["detail"])

    def test_successful_list_retrieval_paginated(self):
        """Test successful retrieval of paginated issues list."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
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

        # Verify ordering by -intake_date
        intake_dates = [issue['intake_date'] for issue in response_data['results']]
        assert intake_dates == sorted(intake_dates, reverse=True)

    def test_issue_response_format_structure_paginated(self):
        """Test that the paginated issues response format matches expected structure."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
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
        first_issue = response_data['results'][0]
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
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK

        # Find a specific issue by id
        network_issue = next((issue for issue in response_data['results'] if issue['id'] == self.issue1.id), None)
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
        assert reporter['id'] == self.user.id
        assert reporter['name'] == self.user.name

        # Test assignee structure
        assignee = network_issue['assignee']
        assert assignee['id'] == self.user.id
        assert assignee['name'] == self.user.name

    def test_empty_list_when_no_issues(self):
        """Test paginated response when no issues exist."""
        # Delete all issues
        Issue.objects.all().delete()

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response_data, dict)
        assert response_data['count'] == 0
        assert response_data['next'] is None
        assert response_data['previous'] is None
        assert isinstance(response_data['results'], list)
        assert len(response_data['results']) == 0

    def test_single_issue_response(self):
        """Test paginated response when only one issue exists."""
        # Delete all but one issue
        Issue.objects.exclude(id=self.issue1.id).delete()

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response_data, dict)
        assert response_data['count'] == 1
        assert response_data['next'] is None
        assert response_data['previous'] is None
        assert len(response_data['results']) == 1
        issue_data = response_data['results'][0]

        # Basic fields
        assert issue_data['tracking_code'] == self.issue1.tracking_code

        # Date field
        assert 'intake_date' in issue_data
        assert issue_data['intake_date'] == self.issue1.intake_date.isoformat().replace('+00:00', 'Z')

        # Foreign key fields
        # Status
        issue_status = issue_data['status']
        assert issue_status['id'] == self.status_open.id
        assert issue_status['name'] == self.status_open.name
        assert issue_status['final_status'] == self.status_open.final_status
        assert issue_status['initial_status'] == self.status_open.initial_status
        assert issue_status['rejected_status'] == self.status_open.rejected_status
        assert issue_status['open_status'] == self.status_open.open_status

        # Category
        category = issue_data['category']
        assert category['id'] == self.category_env.id
        assert category['name'] == self.category_env.name

        # Issue type
        issue_type = issue_data['issue_type']
        assert issue_type['id'] == self.issue_type_complaint.id
        assert issue_type['name'] == self.issue_type_complaint.name

        # Administrative region
        admin_region = issue_data['administrative_region']
        assert admin_region['administrative_id'] == str(self.admin_region.id)
        assert admin_region['name'] == self.admin_region.name

        # Reporter
        reporter = issue_data['reporter']
        assert reporter['id'] == self.user.id
        assert reporter['name'] == self.user.name

        # Assignee
        assignee = issue_data['assignee']
        assert assignee['id'] == self.user.id
        assert assignee['name'] == self.user.name

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

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK
        assert response1.data['count'] == response2.data['count']
        assert len(response1.data['results']) == len(response2.data['results'])

        # Responses should be identical (same data for all users)
        for i, issue in enumerate(response1.data['results']):
            assert issue['id'] == response2.data['results'][i]['id']
            assert issue['tracking_code'] == response2.data['results'][i]['tracking_code']
            assert issue['intake_date'] == response2.data['results'][i]['intake_date']
            assert issue['status'] == response2.data['results'][i]['status']
            assert issue['category'] == response2.data['results'][i]['category']
            assert issue['issue_type'] == response2.data['results'][i]['issue_type']
            assert issue['administrative_region'] == response2.data['results'][i]['administrative_region']
            assert issue['reporter'] == response2.data['results'][i]['reporter']
            assert issue['assignee'] == response2.data['results'][i]['assignee']

    def test_inactive_user_authentication(self):
        """Test that inactive users cannot authenticate."""
        # Create inactive user
        inactive_user = UserFactory(is_active=False)
        inactive_token = Token.objects.create(user=inactive_user)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {inactive_token.key}')
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_large_dataset_performance(self):
        """Test paginated response with a larger dataset of issues."""
        # Create many more issues
        categories_batch = []
        for i in range(50):
            categories_batch.append(
                IssueFactory(
                    administrative_region=self.admin_region, citizen=self.citizen, description="Issue description"
                )
            )

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
        assert response_data['count'] == 52  # 2 original + 50 new
        assert len(response_data['results']) == 20  # Default page size

        # Should have next page
        assert response_data['next'] is not None
        assert response_data['previous'] is None  # First page

        # Verify they're still properly ordered
        intake_dates = [issue['intake_date'] for issue in response_data['results']]
        assert intake_dates == sorted(intake_dates, reverse=True)

    def test_content_type_header(self):
        """Test that the response has correct content type."""
        self.authenticate_with_token()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert 'application/json' in response.get('Content-Type', '')

    def test_get_method_only_allowed(self):
        """Test that only GET method is allowed."""
        self.authenticate_with_token()

        # POST should not be allowed
        response_post = self.client.post(self.url, {})
        assert response_post.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # PUT should not be allowed
        response_put = self.client.put(self.url, {})
        assert response_put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # DELETE should not be allowed
        response_delete = self.client.delete(self.url)
        assert response_delete.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # PATCH should not be allowed
        response_patch = self.client.patch(self.url, {})
        assert response_patch.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # GET should work
        response_get = self.client.get(self.url)
        assert response_get.status_code == status.HTTP_200_OK

    def test_complete_issue_data_integrity(self):
        """Test that all issue data is correctly serialized and maintains integrity."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK

        # Test the first issue completely (issue1 from setUp)
        issue_result = next((i for i in response_data['results'] if i['id'] == self.issue1.id), None)
        assert issue_result is not None

        # Verify main fields
        assert issue_result['id'] == self.issue1.id
        assert issue_result['tracking_code'] == self.issue1.tracking_code
        # intake_date serialized as ISO format string
        assert issue_result['intake_date'] == self.issue1.intake_date.isoformat().replace('+00:00', 'Z')

        # Verify foreign key structures
        assert issue_result['status']['id'] == self.issue1.status.id
        assert issue_result['status']['name'] == "Open"

        assert issue_result['category']['id'] == self.issue1.category.id
        assert issue_result['category']['name'] == "Environmental"

        assert issue_result['issue_type']['id'] == self.issue1.issue_type.id
        assert issue_result['issue_type']['name'] == "Complaint"

        assert issue_result['administrative_region']['administrative_id'] == str(self.issue1.administrative_region.id)
        assert issue_result['administrative_region']['name'] == "KADJÈRÈ"

        assert issue_result['reporter']['id'] == self.issue1.reporter.id
        assert issue_result['reporter']['name'] == self.user.name

        assert issue_result['assignee']['id'] == self.issue1.assignee.id
        assert issue_result['assignee']['name'] == self.user.name
