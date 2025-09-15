import pytest
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeLevelFactory,
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
    IssueSubTypeFactory,
)
from issues.models import IssueCategory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class IssueCategoryListAPIViewTest(APITestCase):
    """
    Test cases for the IssueCategory list API endpoint using Token Authentication.

    This test class covers various scenarios including authentication,
    data retrieval, department serialization, and response format validation.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
    }

    def setUp(self):
        """Set up test data, user, token, and URL for each test."""
        self.url = reverse("issues:list-issue-categories")

        reset_sequences()

        # Create test user and token
        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)

        # Create test administrative levels
        self.district_level = AdministrativeLevelFactory(name="District")
        self.county_level = AdministrativeLevelFactory(name="County")
        self.sub_county_level = AdministrativeLevelFactory(name="Sub-County")

        # Create test departments
        self.env_dept = IssueDepartmentFactory(name="Environmental Department")
        self.appeals_dept = IssueDepartmentFactory(name="Appeals Board")
        self.monitoring_dept = IssueDepartmentFactory(name="Monitoring and Evaluation")

        # Create department-administrative level relationships
        self.env_dept_district = IssueDepartmentAdministrativeLevelFactory(
            department=self.env_dept, administrative_level=self.district_level
        )
        self.appeals_dept_county = IssueDepartmentAdministrativeLevelFactory(
            department=self.appeals_dept, administrative_level=self.county_level
        )
        self.monitoring_dept_subcounty = IssueDepartmentAdministrativeLevelFactory(
            department=self.monitoring_dept, administrative_level=self.sub_county_level
        )
        self.parent = IssueSubTypeFactory(name="Denunciation")

        # Create test issue categories
        self.environmental = IssueCategoryFactory(
            name="Environmental",
            abbreviation="ENV",
            assigned_department=self.env_dept_district,
            assigned_appeal_department=self.appeals_dept_county,
            assigned_escalation_department=self.monitoring_dept_subcounty,
            confidentiality_level="Public",
            redirection_protocol=1,
            parent=self.parent,
        )
        self.corruption = IssueCategoryFactory(
            name="Corruption",
            abbreviation="COR",
            assigned_department=self.appeals_dept_county,
            assigned_appeal_department=self.monitoring_dept_subcounty,
            assigned_escalation_department=self.env_dept_district,
            confidentiality_level="Confidential",
            redirection_protocol=2,
            parent=self.parent,
        )
        self.abuse = IssueCategoryFactory(
            name="Abuse of Office",
            abbreviation="AOF",
            assigned_department=self.monitoring_dept_subcounty,
            assigned_appeal_department=self.env_dept_district,
            assigned_escalation_department=self.appeals_dept_county,
            confidentiality_level="Restricted",
            redirection_protocol=0,
            parent=self.parent,
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
        """Test successful retrieval of paginated issue categories list."""
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
        assert response_data['count'] == 3
        assert response_data['previous'] is None  # First page
        assert response_data['next'] is None  # Only one page needed
        assert isinstance(response_data['results'], list)
        assert len(response_data['results']) == 3

        # Verify ordering (alphabetical by name)
        category_names = [category['name'] for category in response_data['results']]
        expected_order = ['Abuse of Office', 'Corruption', 'Environmental']
        assert category_names == expected_order

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
        first_category = response_data['results'][0]
        expected_fields = [
            'id',
            'name',
            'abbreviation',
            'assigned_department',
            'assigned_appeal_department',
            'assigned_escalation_department',
            'parent_id',
            'confidentiality_level',
            'redirection_protocol',
            'label',
            'value',
        ]

        for field in expected_fields:
            assert field in first_category

        # Verify data types
        assert isinstance(first_category['id'], int)
        assert isinstance(first_category['name'], str)
        assert isinstance(first_category['label'], str)
        assert isinstance(first_category['value'], int)
        assert isinstance(first_category['redirection_protocol'], int)
        assert isinstance(first_category['parent_id'], int)

        # Check department structure
        dept_fields = ['name', 'id', 'administrative_level']
        for dept_field in ['assigned_department', 'assigned_appeal_department', 'assigned_escalation_department']:
            assert isinstance(first_category[dept_field], dict)
            for field in dept_fields:
                assert field in first_category[dept_field]

    def test_department_serialization_structure(self):
        """Test that department fields are properly serialized with correct structure."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200

        # Find the environmental category
        environmental_category = next((cat for cat in response_data['results'] if cat['name'] == 'Environmental'), None)
        assert environmental_category is not None

        # Test assigned_department structure
        assigned_dept = environmental_category['assigned_department']
        assert assigned_dept['name'] == "Environmental Department"
        assert assigned_dept['id'] == self.env_dept.id
        assert assigned_dept['administrative_level'] == "District"

        # Test assigned_appeal_department structure
        appeal_dept = environmental_category['assigned_appeal_department']
        assert appeal_dept['name'] == "Appeals Board"
        assert appeal_dept['id'] == self.appeals_dept.id
        assert appeal_dept['administrative_level'] == "County"

        # Test assigned_escalation_department structure
        escalation_dept = environmental_category['assigned_escalation_department']
        assert escalation_dept['name'] == "Monitoring and Evaluation"
        assert escalation_dept['id'] == self.monitoring_dept.id
        assert escalation_dept['administrative_level'] == "Sub-County"

    def test_label_and_value_fields(self):
        """Test that label and value convenience fields are properly set."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200

        for category in response_data['results']:
            # Label should match name
            assert category['label'] == category['name']
            # Value should match id
            assert category['value'] == category['id']

    def test_empty_list_when_no_categories(self):
        """Test paginated response when no issue categories exist."""
        # Delete all categories
        IssueCategory.objects.all().delete()

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

    def test_single_category_response(self):
        """Test paginated response when only one category exists."""
        # Delete all but one category
        IssueCategory.objects.exclude(id=self.environmental.id).delete()

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert isinstance(response_data, dict)
        assert response_data['count'] == 1
        assert response_data['next'] is None
        assert response_data['previous'] is None
        assert len(response_data['results']) == 1
        assert response_data['results'][0]['name'] == self.environmental.name
        assert response_data['results'][0]['id'] == self.environmental.id
        assert response_data['results'][0]['label'] == self.environmental.name
        assert response_data['results'][0]['value'] == self.environmental.id

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
        """Test paginated response with a larger dataset of categories."""
        # Create many more categories
        categories_batch = []
        for i in range(50):
            categories_batch.append(
                IssueCategoryFactory(
                    name=f"Category {i:02d}",
                    assigned_department=self.env_dept_district,
                    assigned_appeal_department=self.appeals_dept_county,
                    assigned_escalation_department=self.monitoring_dept_subcounty,
                )
            )

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200
        assert response_data['count'] == 53  # 3 original + 50 new
        assert len(response_data['results']) == 20  # Default page size

        # Should have next page
        assert response_data['next'] is not None
        assert response_data['previous'] is None  # First page

        # Verify they're still properly ordered
        category_names = [category['name'] for category in response_data['results']]
        assert category_names == sorted(category_names)

    def test_category_ordering_case_insensitive(self):
        """Test that category ordering is case-insensitive in paginated response."""
        # Create categories with different cases
        IssueCategoryFactory(
            name="Apple Issues",
            assigned_department=self.env_dept_district,
            assigned_appeal_department=self.appeals_dept_county,
            assigned_escalation_department=self.monitoring_dept_subcounty,
        )
        IssueCategoryFactory(
            name="Banana Problems",
            assigned_department=self.env_dept_district,
            assigned_appeal_department=self.appeals_dept_county,
            assigned_escalation_department=self.monitoring_dept_subcounty,
        )

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200

        # Extract names and verify alphabetical ordering
        category_names = [category['name'] for category in response_data['results']]

        # Should be ordered alphabetically regardless of case
        expected_start = ['Abuse of Office', 'Apple Issues', 'Banana Problems', 'Corruption']
        actual_start = category_names[:4]
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

    def test_abbreviation_field_nullable(self):
        """Test that abbreviation field can be null or blank."""
        # Create category without abbreviation
        IssueCategoryFactory(
            name="No Abbreviation Category",
            abbreviation=None,
            assigned_department=self.env_dept_district,
            assigned_appeal_department=self.appeals_dept_county,
            assigned_escalation_department=self.monitoring_dept_subcounty,
        )

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200

        # Find the category without abbreviation
        no_abbrev_result = next(
            (cat for cat in response_data['results'] if cat['name'] == 'No Abbreviation Category'), None
        )
        assert no_abbrev_result is not None
        assert no_abbrev_result['abbreviation'] is None

    def test_confidentiality_level_field_nullable(self):
        """Test that confidentiality_level field can be null or blank."""
        # Create category without confidentiality level
        IssueCategoryFactory(
            name="No Confidentiality Category",
            confidentiality_level=None,
            assigned_department=self.env_dept_district,
            assigned_appeal_department=self.appeals_dept_county,
            assigned_escalation_department=self.monitoring_dept_subcounty,
        )

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200

        # Find the category without confidentiality level
        no_conf_result = next(
            (cat for cat in response_data['results'] if cat['name'] == 'No Confidentiality Category'), None
        )
        assert no_conf_result is not None
        assert no_conf_result['confidentiality_level'] is None

    def test_parent_field_nullable(self):
        """Test that parent field can be null or blank."""
        # Create category without parent
        IssueCategoryFactory(
            name="No Parent Category",
            parent=None,
            assigned_department=self.env_dept_district,
            assigned_appeal_department=self.appeals_dept_county,
            assigned_escalation_department=self.monitoring_dept_subcounty,
        )

        self.authenticate_with_token()
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200

        # Find the category without parent
        no_parent_result = next((cat for cat in response_data['results'] if cat['name'] == 'No Parent Category'), None)
        assert no_parent_result is not None
        assert no_parent_result['parent_id'] is None

    def test_complete_category_data_integrity(self):
        """Test that all category data is correctly serialized and maintains integrity."""
        self.authenticate_with_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == 200

        # Test environmental category completely
        environmental_result = next((cat for cat in response_data['results'] if cat['name'] == 'Environmental'), None)
        assert environmental_result is not None

        # Verify all fields
        assert environmental_result['id'] == self.environmental.id
        assert environmental_result['name'] == 'Environmental'
        assert environmental_result['abbreviation'] == 'ENV'
        assert environmental_result['confidentiality_level'] == 'Public'
        assert environmental_result['redirection_protocol'] == 1
        assert environmental_result['label'] == 'Environmental'
        assert environmental_result['value'] == self.environmental.id
        assert environmental_result['parent_id'] == self.parent.id

        # Verify department structures
        assert environmental_result['assigned_department']['name'] == 'Environmental Department'
        assert environmental_result['assigned_department']['id'] == self.env_dept.id
        assert environmental_result['assigned_department']['administrative_level'] == 'District'

        assert environmental_result['assigned_appeal_department']['name'] == 'Appeals Board'
        assert environmental_result['assigned_appeal_department']['id'] == self.appeals_dept.id
        assert environmental_result['assigned_appeal_department']['administrative_level'] == 'County'

        assert environmental_result['assigned_escalation_department']['name'] == 'Monitoring and Evaluation'
        assert environmental_result['assigned_escalation_department']['id'] == self.monitoring_dept.id
        assert environmental_result['assigned_escalation_department']['administrative_level'] == 'Sub-County'
