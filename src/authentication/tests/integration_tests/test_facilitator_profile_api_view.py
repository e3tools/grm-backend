import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.constants import FACILITATOR_NOT_FOUND_ERROR_MESSAGE
from authentication.factories import FacilitatorFactory, UserFactory
from issues.factories import AdministrativeRegionFactory, IssueDepartmentFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class FacilitatorProfileAPIViewTest(APITestCase):
    """
    Test cases for the Facilitator Profile API endpoint using Token Authentication.

    This test class covers various scenarios including authentication,
    facilitator validation, and response format validation.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
    }

    def setUp(self):
        """Set up test data, users, tokens, and URL for each test."""

        # Create test users
        self.facilitator_user = UserFactory()
        self.non_facilitator_user = UserFactory()

        # Create tokens
        self.facilitator_token = Token.objects.create(user=self.facilitator_user)
        self.non_facilitator_token = Token.objects.create(user=self.non_facilitator_user)

        # Create department
        self.department = IssueDepartmentFactory(name="Public Works")

        # Create administrative region
        self.admin_region = AdministrativeRegionFactory(parent=AdministrativeRegionFactory())

        # Create facilitator with complete data
        self.facilitator = FacilitatorFactory(
            user=self.facilitator_user,
            department=self.department,
            administrative_region=self.admin_region,
            unique_region=True,
            village_secretary=False,
        )

        self.url = reverse("authentication:facilitator-profile")

    def authenticate_with_facilitator_token(self):
        """Helper method to authenticate client with facilitator token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.facilitator_token.key}')

    def authenticate_with_non_facilitator_token(self):
        """Helper method to authenticate client with non-facilitator token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.non_facilitator_token.key}')

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

    def test_facilitator_profile_response_format_structure(self):
        """Test that the facilitator profile response format matches expected structure."""
        self.authenticate_with_facilitator_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response_data, dict)

        # Check all main fields
        expected_fields = [
            'id',
            'user',
            'department',
            'administrative_region',
            'unique_region',
            'village_secretary',
            'created_date',
            'updated_date',
        ]
        for field in expected_fields:
            assert field in response_data

        # Verify data types
        assert isinstance(response_data['id'], int)
        assert isinstance(response_data['user'], dict)
        assert isinstance(response_data['unique_region'], bool)
        assert isinstance(response_data['created_date'], str)
        assert isinstance(response_data['updated_date'], str)

        # Check user structure
        user = response_data['user']
        assert 'id' in user
        assert 'name' in user
        assert isinstance(user['id'], int)
        assert isinstance(user['name'], str)

        # Check department structure
        if response_data['department'] is not None:
            department = response_data['department']
            assert isinstance(department, dict)
            assert 'id' in department
            assert 'name' in department
            assert 'created_date' in department
            assert 'updated_date' in department

        # Check administrative_region structure
        if response_data['administrative_region'] is not None:
            admin_region = response_data['administrative_region']
            assert isinstance(admin_region, dict)
            assert 'id' in admin_region
            assert 'name' in admin_region
            assert 'administrative_level' in admin_region
            assert 'parent' in admin_region
            assert 'created_date' in admin_region
            assert 'updated_date' in admin_region

    def test_facilitator_complete_profile_data(self):
        """Test facilitator with complete profile data returns all information correctly."""
        self.authenticate_with_facilitator_token()

        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK

        # Verify facilitator basic fields
        assert response_data['id'] == self.facilitator.id
        assert response_data['unique_region'] is True
        assert response_data['village_secretary'] is False

        # Verify user data
        user = response_data['user']
        assert user['id'] == self.facilitator_user.id
        assert user['name'] == self.facilitator_user.name

        # Verify department data
        department = response_data['department']
        assert department is not None
        assert department['id'] == self.department.id
        assert department['name'] == "Public Works"
        assert 'created_date' in department
        assert 'updated_date' in department

        # Verify administrative_region data
        admin_region = response_data['administrative_region']
        administrative_region = self.facilitator.administrative_region
        assert admin_region is not None
        assert admin_region['id'] == administrative_region.id
        assert admin_region['name'] == administrative_region.name
        assert admin_region['administrative_level'] == administrative_region.administrative_level.id
        assert admin_region['parent'] == administrative_region.parent.id
        assert 'created_date' in admin_region
        assert 'updated_date' in admin_region

    def test_facilitator_without_department(self):
        """Test facilitator without department returns null for department field."""
        # Create facilitator without department
        user_without_dept = UserFactory()
        token_without_dept = Token.objects.create(user=user_without_dept)
        FacilitatorFactory(
            user=user_without_dept,
            department=None,
            administrative_region=self.admin_region,
            unique_region=True,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token_without_dept.key}')
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
        assert response_data['department'] is None
        assert response_data['administrative_region'] is not None

    def test_facilitator_without_administrative_region(self):
        """Test facilitator without administrative region returns null."""
        # Create facilitator without administrative region
        user_without_region = UserFactory()
        token_without_region = Token.objects.create(user=user_without_region)
        FacilitatorFactory(
            user=user_without_region,
            department=self.department,
            administrative_region=None,
            unique_region=False,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token_without_region.key}')
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
        assert response_data['unique_region'] is False
        assert response_data['administrative_region'] is None
        assert response_data['department'] is not None

    def test_facilitator_minimal_data(self):
        """Test facilitator with minimal data (no department, no region)."""
        user_minimal = UserFactory()
        token_minimal = Token.objects.create(user=user_minimal)
        FacilitatorFactory(
            user=user_minimal,
            department=None,
            administrative_region=None,
            unique_region=None,
            village_secretary=None,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token_minimal.key}')
        response = self.client.get(self.url)
        response_data = response.data

        assert response.status_code == status.HTTP_200_OK
        assert response_data['department'] is None
        assert response_data['administrative_region'] is None
        assert response_data['unique_region'] is None
        assert response_data['village_secretary'] is None

    def test_non_facilitator_user_returns_404(self):
        """Test that non-facilitator user receives 404 error."""
        self.authenticate_with_non_facilitator_token()

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data
        assert response.data['error'] == FACILITATOR_NOT_FOUND_ERROR_MESSAGE

    def test_inactive_user_authentication(self):
        """Test that inactive users cannot authenticate."""
        self.facilitator_user.is_active = False
        self.facilitator_user.save()

        self.authenticate_with_facilitator_token()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_content_type_header(self):
        """Test that the response has correct content type."""
        self.authenticate_with_facilitator_token()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert 'application/json' in response.get('Content-Type', '')

    def test_get_method_only_allowed(self):
        """Test that only GET method is allowed."""
        self.authenticate_with_facilitator_token()

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

    def test_unique_region_true(self):
        """Test facilitator with unique_region=True."""
        self.authenticate_with_facilitator_token()

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['unique_region'] is True

    def test_unique_region_false(self):
        """Test facilitator with unique_region=False."""
        self.facilitator.unique_region = False
        self.facilitator.save()

        self.authenticate_with_facilitator_token()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['unique_region'] is False

    def test_unique_region_null(self):
        """Test facilitator with unique_region=None."""
        self.facilitator.unique_region = None
        self.facilitator.save()

        self.authenticate_with_facilitator_token()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['unique_region'] is None

    def test_village_secretary_true(self):
        """Test facilitator with village_secretary=True."""
        self.facilitator.village_secretary = True
        self.facilitator.save()

        self.authenticate_with_facilitator_token()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['village_secretary'] is True

    def test_village_secretary_false(self):
        """Test facilitator with village_secretary=False."""
        self.authenticate_with_facilitator_token()

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['village_secretary'] is False

    def test_department_serialization_fields(self):
        """Test that department contains all required serialized fields."""
        self.authenticate_with_facilitator_token()

        response = self.client.get(self.url)
        department = response.data['department']

        assert response.status_code == status.HTTP_200_OK
        assert department is not None

        # Check all fields from IssueDepartmentSerializer
        required_fields = ['id', 'name', 'created_date', 'updated_date']
        for field in required_fields:
            assert field in department, f"Field '{field}' missing in department"

        # Verify field types
        assert isinstance(department['id'], int)
        assert isinstance(department['name'], str)
        assert isinstance(department['created_date'], str)
        assert isinstance(department['updated_date'], str)

    def test_administrative_region_serialization_fields(self):
        """Test that administrative_region contains all required serialized fields."""
        self.authenticate_with_facilitator_token()

        response = self.client.get(self.url)
        admin_region = response.data['administrative_region']

        assert response.status_code == status.HTTP_200_OK
        assert admin_region is not None

        # Check all fields from AdministrativeRegionSerializer
        required_fields = ['id', 'name', 'administrative_level', 'parent', 'created_date', 'updated_date']
        for field in required_fields:
            assert field in admin_region, f"Field '{field}' missing in administrative_region"

        # Verify field types
        assert isinstance(admin_region['id'], int)
        assert isinstance(admin_region['name'], str)
        assert isinstance(admin_region['administrative_level'], int)
        assert isinstance(admin_region['parent'], int)
        assert isinstance(admin_region['created_date'], str)
        assert isinstance(admin_region['updated_date'], str)

    def test_user_serialization_fields(self):
        """Test that user contains all required serialized fields."""
        self.authenticate_with_facilitator_token()

        response = self.client.get(self.url)
        user = response.data['user']

        assert response.status_code == status.HTTP_200_OK
        assert user is not None

        # Check all fields
        required_fields = ['id', 'name']
        for field in required_fields:
            assert field in user, f"Field '{field}' missing in user"

        # Verify field types and values
        assert isinstance(user['id'], int)
        assert isinstance(user['name'], str)
        assert user['id'] == self.facilitator_user.id
        assert user['name'] == self.facilitator_user.name

    def test_profile_timestamps(self):
        """Test that created_date and updated_date are present and properly formatted."""
        self.authenticate_with_facilitator_token()

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert 'created_date' in response.data
        assert 'updated_date' in response.data

        # Verify timestamps are in ISO format strings
        assert isinstance(response.data['created_date'], str)
        assert isinstance(response.data['updated_date'], str)

        # Basic format validation (should contain 'T' for datetime ISO format)
        assert 'T' in response.data['created_date']
        assert 'T' in response.data['updated_date']
