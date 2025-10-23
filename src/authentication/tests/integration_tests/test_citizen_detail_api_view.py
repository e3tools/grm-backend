import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import CitizenFactory, UserFactory
from grm.constants import MALE_CHOICE
from issues.factories import CitizenAgeGroupFactory
from issues.factories import CitizenFactory as IssuesCitizenFactory
from issues.factories import CitizenGroupFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class CitizenDetailAPIViewTest(APITestCase):
    """
    Integration tests for CitizenDetailAPIView (GET).
    Verifies authentication, structure, and nested serialization.
    """

    def setUp(self):
        """Set up data for each test."""
        self.user = UserFactory(
            first_name="John",
            last_name="Doe",
            phone_number="123456789",
            email="john.doe@example.com",
        )
        self.token = Token.objects.create(user=self.user)

        # Create related issue-level citizen data
        self.age_group = CitizenAgeGroupFactory()
        self.group = CitizenGroupFactory()
        self.group_2 = CitizenGroupFactory()

        self.issues_citizen = IssuesCitizenFactory(
            name="John Doe",
            age_group=self.age_group,
            gender=MALE_CHOICE,
            group=self.group,
            group_2=self.group_2,
        )

        self.citizen = CitizenFactory(user=self.user, citizen=self.issues_citizen)
        self.url = reverse("authentication:citizen-detail")

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_authentication_required(self):
        """Test that request without credentials is unauthorized."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authentication credentials were not provided.", str(response.data["detail"]))

    def test_invalid_token(self):
        """Test that invalid token returns 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Token invalid123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_successful_retrieval(self):
        """Test successful GET with serialized nested objects."""
        self.authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Check top-level user fields
        self.assertEqual(data["first_name"], self.user.first_name)
        self.assertEqual(data["last_name"], self.user.last_name)
        self.assertEqual(data["phone_number"], self.user.phone_number)
        self.assertEqual(data["email"], self.user.email)

        citizen = self.user.citizen.citizen

        # Check gender
        self.assertEqual(data["gender"], citizen.gender)

        # Check nested age_group serialization
        self.assertIsInstance(data["age_group"], dict)
        self.assertEqual(data["age_group"]["id"], citizen.age_group.id)
        self.assertEqual(data["age_group"]["name"], citizen.age_group.name)

        # Check nested group serialization
        self.assertIsInstance(data["group"], dict)
        self.assertEqual(data["group"]["id"], citizen.group.id)
        self.assertEqual(data["group"]["name"], citizen.group.name)
        self.assertEqual(data["group"]["type"], citizen.group.type)

        # Check nested group_2 serialization
        self.assertIsInstance(data["group_2"], dict)
        self.assertEqual(data["group_2"]["id"], citizen.group_2.id)
        self.assertEqual(data["group_2"]["name"], citizen.group_2.name)
        self.assertEqual(data["group_2"]["type"], citizen.group_2.type)

        # Check datetime fields
        self.assertEqual(data["created_date"], citizen.created_date)
        self.assertEqual(data["updated_date"], citizen.updated_date)

    def test_get_method_only_allowed(self):
        """Test that only GET method is allowed."""
        self.authenticate()

        # POST should not be allowed
        response_post = self.client.post(self.url, {})
        self.assertEqual(response_post.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT should not be allowed
        response_put = self.client.put(self.url, {})
        self.assertEqual(response_put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE should not be allowed
        response_delete = self.client.delete(self.url)
        self.assertEqual(response_delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH should not be allowed
        response_patch = self.client.patch(self.url, {})
        self.assertEqual(response_patch.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # GET should work
        response_get = self.client.get(self.url)
        self.assertEqual(response_get.status_code, status.HTTP_200_OK)

    def test_authenticated_without_citizen_returns_404(self):
        """Authenticated user without a Citizen should get 404."""
        self.authenticate()
        self.issues_citizen.delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("Not found", str(response.data["detail"]))
