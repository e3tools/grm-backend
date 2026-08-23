import pytest
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
from issues.factories import AdministrativeLevelFactory, AdministrativeRegionFactory
from issues.models import AdministrativeRegion


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class AdministrativeRegionListAPIViewTest(APITestCase):
    """
    Test cases for the AdministrativeRegion list API endpoint (paginated).

    Covers authentication, pagination, response structure, and ordering.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
    }

    def setUp(self):
        """Set up user, token, and initial regions for tests."""
        self.url = reverse("issues:list-regions")

        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)
        self.child_level = AdministrativeLevelFactory()

        # Create multiple regions
        self.region_a = AdministrativeRegionFactory(name="Alpha", parent=None)
        self.region_b = AdministrativeRegionFactory(
            name="Beta", parent=self.region_a, administrative_level=self.child_level
        )
        self.region_c = AdministrativeRegionFactory(
            name="Charlie", parent=self.region_a, administrative_level=self.child_level
        )

    def authenticate(self):
        """Helper to authenticate client."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_authentication_required_no_credentials(self):
        """Test that authentication is required."""
        response = self.client.get(self.url)
        assert response.status_code == 401
        assert self.error_messages["authentication"] in str(response.data["detail"])

    def test_authentication_required_invalid_token(self):
        """Test authentication with invalid token."""
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid_token_123')
        response = self.client.get(self.url)
        assert response.status_code == 401
        assert self.error_messages["invalid_token"] in str(response.data["detail"])

    def test_successful_paginated_list_retrieval(self):
        """Test successful retrieval of paginated administrative regions list."""
        self.authenticate()
        response = self.client.get(self.url)

        assert response.status_code == 200
        assert isinstance(response.data, dict)
        assert 'count' in response.data
        assert 'next' in response.data
        assert 'previous' in response.data
        assert 'results' in response.data

        assert response.data['count'] == 3
        assert isinstance(response.data['results'], list)
        names = [r['name'] for r in response.data['results']]
        assert names == ['Alpha', 'Beta', 'Charlie']  # Ordered alphabetically

        # Check structure of first child in results
        first_child = response.data['results'][1]
        expected_fields = [
            'id',
            'name',
            'hierarchical_name',
            'administrative_level',
            'parent',
            'created_date',
            'updated_date',
        ]

        for field in expected_fields:
            assert field in first_child

        # Verify data types
        assert isinstance(first_child['id'], int)
        assert isinstance(first_child['name'], str)
        assert isinstance(first_child['hierarchical_name'], str)
        assert isinstance(first_child['administrative_level'], int)
        assert isinstance(first_child['parent'], int)
        assert isinstance(first_child['created_date'], str)
        assert isinstance(first_child['updated_date'], str)

        # Verify data
        assert first_child['id'] == self.region_b.id
        assert first_child['name'] == self.region_b.name
        assert first_child['hierarchical_name'] == self.region_b.hierarchical_name
        assert first_child['administrative_level'] == self.region_b.administrative_level.id
        assert first_child['parent'] == self.region_b.parent.id

    def test_empty_list_when_no_regions(self):
        """Test paginated response when there are no regions."""
        AdministrativeRegion.objects.all().delete()
        self.authenticate()

        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data['count'] == 0
        assert isinstance(response.data['results'], list)
        assert len(response.data['results']) == 0

    def test_single_region_response(self):
        """Test response when only one region exists."""
        AdministrativeRegion.objects.exclude(id=self.region_a.id).delete()
        self.authenticate()

        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data['count'] == 1
        assert len(response.data['results']) == 1
        region = response.data['results'][0]
        assert region['name'] == 'Alpha'
        assert region['administrative_level'] == self.region_a.administrative_level.id
        assert region['parent'] is None
        assert 'created_date' in region
        assert 'updated_date' in region

    def test_pagination_with_large_dataset(self):
        """Test pagination when there are many regions."""
        AdministrativeRegionFactory.create_batch(50, parent=self.region_a, administrative_level=self.child_level)
        self.authenticate()

        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data['count'] >= 53
        assert len(response.data['results']) == 20
        assert response.data['next'] is not None
        assert response.data['previous'] is None

    def test_response_content_type(self):
        """Test that response has correct content type."""
        self.authenticate()
        response = self.client.get(self.url)
        assert 'application/json' in response.get('Content-Type', '')

    def test_get_method_only_allowed(self):
        """Test that only GET is allowed."""
        self.authenticate()

        response_post = self.client.post(self.url, {})
        response_put = self.client.put(self.url, {})
        response_delete = self.client.delete(self.url)
        response_patch = self.client.patch(self.url, {})

        assert response_post.status_code == 405
        assert response_put.status_code == 405
        assert response_delete.status_code == 405
        assert response_patch.status_code == 405

        response_get = self.client.get(self.url)
        assert response_get.status_code == 200
