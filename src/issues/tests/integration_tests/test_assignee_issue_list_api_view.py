import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
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
)
from issues.models import Issue


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class AssigneeIssueListAPIViewTest(APITestCase):
    """
    Test cases for the Issue list API endpoint filtered by the authenticated user as assignee.

    This test class covers various scenarios including authentication,
    data retrieval, pagination, and response format validation.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
    }

    def setUp(self):
        """Set up test data, user, token, and URL for each test."""
        self.url = reverse("issues:list-assigned-issues")

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

        # Create issues assigned to the test user
        self.issue1 = IssueFactory(
            status=self.status_open,
            category=self.category_env,
            issue_type=self.issue_type_complaint,
            administrative_region=self.admin_region,
            assignee=self.user,
            citizen=self.citizen,
            description="Network connectivity issue",
        )
        self.issue2 = IssueFactory(
            status=self.status_open,
            category=self.category_env,
            issue_type=self.issue_type_complaint,
            administrative_region=self.admin_region,
            assignee=self.user,
            citizen=self.citizen,
            description="Water pollution complaint",
        )

        # Create an issue assigned to another user (should not appear in authenticated user’s results)
        self.other_user = UserFactory()
        self.issue_other = IssueFactory(
            status=self.status_open,
            category=self.category_env,
            issue_type=self.issue_type_complaint,
            administrative_region=self.admin_region,
            assignee=self.other_user,
            citizen=self.citizen,
            description="Other user issue",
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
        assert reporter['id'] == self.issue1.reporter.id
        assert reporter['name'] == self.issue1.reporter.name

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
        assert reporter['id'] == self.issue1.reporter.id
        assert reporter['name'] == self.issue1.reporter.name

        # Assignee
        assignee = issue_data['assignee']
        assert assignee['id'] == self.user.id
        assert assignee['name'] == self.user.name

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
                    administrative_region=self.admin_region,
                    citizen=self.citizen,
                    assignee=self.user,
                    description="Issue description",
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

    def test_successful_list_retrieval_only_assigned(self):
        """Test retrieval only returns issues where the authenticated user is assignee."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
        assert response_data['count'] == 2  # only issue1 and issue2 belong to self.user
        issue_ids = [issue['id'] for issue in response_data['results']]
        assert self.issue1.id in issue_ids
        assert self.issue2.id in issue_ids
        assert self.issue_other.id not in issue_ids

    def test_different_users_get_different_results(self):
        """Test that different users only see issues where they are assignee."""
        # First user (self.user)
        self.authenticate_with_token()
        response1 = self.client.get(self.url)

        # Second user (self.other_user)
        token2 = Token.objects.create(user=self.other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token2.key}')
        response2 = self.client.get(self.url)

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK

        # First user sees 2 issues
        assert response1.data['count'] == 2
        issue_ids_user1 = {i['id'] for i in response1.data['results']}
        assert self.issue1.id in issue_ids_user1
        assert self.issue2.id in issue_ids_user1

        # Second user sees 1 issue (only self.issue_other)
        assert response2.data['count'] == 1
        issue_ids_user2 = {i['id'] for i in response2.data['results']}
        assert self.issue_other.id in issue_ids_user2
        assert self.issue1.id not in issue_ids_user2
        assert self.issue2.id not in issue_ids_user2

    def test_filter_by_created_date_returns_only_recent_issues(self):
        """Test filtering issues by created_date only returns those created after the given datetime."""
        self.authenticate_with_token()

        # Force issue1 to be older than issue2
        self.issue1.created_date = self.issue1.created_date.replace(year=self.issue1.created_date.year - 1)
        self.issue1.save(update_fields=["created_date"])

        # Filter by date after issue1
        created_after = self.issue1.created_date.isoformat().replace("+00:00", "Z")
        response = self.client.get(self.url, {"created_date": created_after})

        assert response.status_code == status.HTTP_200_OK
        issue_ids = {i["id"] for i in response.data["results"]}
        assert self.issue2.id in issue_ids
        assert self.issue1.id not in issue_ids

    def test_filter_by_updated_date_returns_only_recently_updated_issues(self):
        """Test filtering issues by updated_date only returns those updated after the given datetime."""
        self.authenticate_with_token()

        # Force issue1 to be updated much earlier
        old_updated_date = self.issue1.updated_date.replace(year=self.issue1.updated_date.year - 1)
        Issue.objects.filter(id=self.issue1.id).update(updated_date=old_updated_date)
        self.issue1.refresh_from_db()

        updated_after = self.issue1.updated_date.isoformat().replace("+00:00", "Z")
        response = self.client.get(self.url, {"updated_date": updated_after})

        assert response.status_code == status.HTTP_200_OK
        issue_ids = {i["id"] for i in response.data["results"]}
        assert self.issue2.id in issue_ids
        assert self.issue1.id not in issue_ids

    def test_filter_by_created_and_updated_date_combined(self):
        """Test filtering issues with both created_date and updated_date applied together."""
        self.authenticate_with_token()

        # Set issue1 as old in created_date and updated_date
        old_created_date = self.issue1.created_date.replace(year=self.issue1.created_date.year - 1)
        old_updated_date = self.issue1.updated_date.replace(year=self.issue1.updated_date.year - 1)
        Issue.objects.filter(id=self.issue1.id).update(created_date=old_created_date, updated_date=old_updated_date)
        self.issue1.refresh_from_db()

        created_after = self.issue1.created_date.isoformat().replace("+00:00", "Z")
        updated_after = self.issue1.updated_date.isoformat().replace("+00:00", "Z")

        response = self.client.get(self.url, {"created_date": created_after, "updated_date": updated_after})

        assert response.status_code == status.HTTP_200_OK
        issue_ids = {i["id"] for i in response.data["results"]}
        assert self.issue2.id in issue_ids
        assert self.issue1.id not in issue_ids

    def test_invalid_created_date_returns_400(self):
        """Test API returns 400 when created_date has invalid format."""
        self.authenticate_with_token()

        response = self.client.get(self.url, {"created_date": "not-a-valid-datetime"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "created_date" in response.data
        assert "Invalid datetime format" in response.data["created_date"]

    def test_invalid_updated_date_returns_400(self):
        """Test API returns 400 when updated_date has invalid format."""
        self.authenticate_with_token()

        response = self.client.get(self.url, {"updated_date": "not-a-valid-datetime"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "updated_date" in response.data
        assert "Invalid datetime format" in response.data["updated_date"]

    def test_empty_created_date(self):
        """Test empty string for created_date does not crash and returns unfiltered queryset."""
        self.authenticate_with_token()

        response = self.client.get(self.url, {"created_date": ""})
        assert response.status_code == status.HTTP_200_OK
        # No crash, normal count
        assert response.data["count"] == 2

    def test_empty_updated_date(self):
        """Test empty string for updated_date does not crash and returns unfiltered queryset."""
        self.authenticate_with_token()

        response = self.client.get(self.url, {"updated_date": ""})
        assert response.status_code == status.HTTP_200_OK
        # No crash, normal count
        assert response.data["count"] == 2
