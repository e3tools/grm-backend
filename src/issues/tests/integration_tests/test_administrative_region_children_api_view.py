import pytest
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import UserFactory
from issues.factories import AdministrativeLevelFactory, AdministrativeRegionFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class AdministrativeRegionChildrenAPIViewTest(APITestCase):
    """
    Test cases for the AdministrativeRegion children API endpoint (no pagination).

    Covers authentication, data retrieval, filtering by parent,
    and validation of response structure and data.
    """

    error_messages = {
        "authentication": "Authentication credentials were not provided.",
        "invalid_token": "Invalid token.",
    }

    def setUp(self):
        """Set up user, token, and initial regions for tests."""
        self.url = reverse("issues:list-region-children")

        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)
        self.child_level = AdministrativeLevelFactory()

        # Create regions hierarchy
        self.region_root = AdministrativeRegionFactory(name="RootRegion", parent=None)
        self.child_a = AdministrativeRegionFactory(
            name="ChildA", parent=self.region_root, administrative_level=self.child_level
        )
        self.child_b = AdministrativeRegionFactory(
            name="ChildB", parent=self.region_root, administrative_level=self.child_level
        )

    def authenticate(self):
        """Helper method to authenticate client with token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_authentication_required_no_credentials(self):
        """Test that authentication is required when no credentials provided."""
        response = self.client.get(self.url)
        assert response.status_code == 401
        assert self.error_messages["authentication"] in str(response.data["detail"])

    def test_authentication_required_invalid_token(self):
        """Test authentication with invalid token."""
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid_token_123')
        response = self.client.get(self.url)
        assert response.status_code == 401
        assert self.error_messages["invalid_token"] in str(response.data["detail"])

    def test_fetch_root_regions_when_parent_is_null(self):
        """Test retrieval of regions with parent=None."""
        self.authenticate()
        response = self.client.get(self.url, {'parent': 'null'})

        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) == 1
        assert response.data[0]['name'] == self.region_root.name
        assert response.data[0]['parent'] is None

    def test_fetch_root_regions_when_no_parent_param(self):
        """Test retrieval of top-level regions when no 'parent' param is provided."""
        self.authenticate()
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['name'] == self.region_root.name

    def test_fetch_children_of_specific_region(self):
        """Test retrieval of child regions for a given parent."""
        self.authenticate()
        response = self.client.get(self.url, {'parent': self.region_root.id})

        assert response.status_code == 200
        assert isinstance(response.data, list)
        names = [r['name'] for r in response.data]
        assert sorted(names) == ['ChildA', 'ChildB']
        for region in response.data:
            assert region['parent'] == self.region_root.id
            assert region['administrative_level'] == self.child_level.id
            assert 'created_date' in region
            assert 'updated_date' in region

    def test_fetch_children_of_region_with_no_children(self):
        """Test when the specified parent has no children."""
        self.authenticate()
        response = self.client.get(self.url, {'parent': self.child_a.id})

        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) == 0

    def test_get_method_only_allowed(self):
        """Test that only GET is allowed on this endpoint."""
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
