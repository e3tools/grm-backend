import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from authentication.factories import CitizenFactory, UserFactory
from authentication.models import Citizen, User
from grm.constants import MALE_CHOICE, OTHER_CHOICE
from issues.factories import CitizenAgeGroupFactory
from issues.factories import CitizenFactory as IssuesCitizenFactory
from issues.factories import CitizenGroupFactory


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class CitizenUpdateAPIViewTest(APITestCase):
    """
    Integration tests for CitizenUpdateAPIView (PATCH).
    Covers authentication, data updates, and field synchronization.
    """

    def setUp(self):
        """Set up initial data for patch tests."""
        self.user = UserFactory(
            first_name="John",
            last_name="Doe",
            phone_number="123456789",
            email="john.doe@example.com",
        )
        self.token = Token.objects.create(user=self.user)

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
        self.url = reverse("authentication:citizen-update")
        self.user_payload = {
            "first_name": "JohnUpdated",
            "last_name": "DoeUpdated",
            "phone_number": "111222333",
            "email": "john.updated@example.com",
        }

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_authentication_required(self):
        """Test patch without authentication returns 401."""
        response = self.client.patch(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authentication credentials were not provided.", str(response.data["detail"]))

    def test_invalid_token(self):
        """Test invalid token returns 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Token bad_token_456")
        response = self.client.patch(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_partial_update_user_fields(self):
        """Test PATCH successfully updates user fields."""
        self.authenticate()

        updated_date = Citizen.objects.get(user=self.user).citizen.updated_date

        response = self.client.patch(self.url, self.user_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        updated_user = User.objects.get(pk=self.user.pk)
        self.assertEqual(updated_user.first_name, self.user_payload.get("first_name"))
        self.assertEqual(updated_user.last_name, self.user_payload.get("last_name"))
        self.assertEqual(updated_user.phone_number, self.user_payload.get("phone_number"))
        self.assertEqual(updated_user.email, self.user_payload.get("email"))

        self.assertEqual(data["first_name"], self.user_payload.get("first_name"))
        self.assertEqual(data["last_name"], self.user_payload.get("last_name"))
        self.assertEqual(data["phone_number"], self.user_payload.get("phone_number"))
        self.assertEqual(data["email"], self.user_payload.get("email"))

        updated_citizen = Citizen.objects.get(user=self.user).citizen
        self.assertNotEqual(updated_date, updated_citizen.updated_date)

    def test_partial_update_citizen_fields(self):
        """Test PATCH updates issues.Citizen-related fields."""
        self.authenticate()

        new_age_group = CitizenAgeGroupFactory()
        new_group = CitizenGroupFactory()
        new_group_2 = CitizenGroupFactory()

        payload = {
            "age_group_id": new_age_group.id,
            "gender": OTHER_CHOICE,
            "group_id": new_group.id,
            "group_2_id": new_group_2.id,
        }

        updated_date = Citizen.objects.get(user=self.user).citizen.updated_date
        response = self.client.patch(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        updated_citizen = Citizen.objects.get(user=self.user).citizen
        self.assertNotEqual(updated_date, updated_citizen.updated_date)

        self.assertEqual(updated_citizen.gender, OTHER_CHOICE)
        self.assertEqual(updated_citizen.age_group_id, new_age_group.id)
        self.assertEqual(updated_citizen.group_id, new_group.id)
        self.assertEqual(updated_citizen.group_2_id, new_group_2.id)

        self.assertEqual(data["gender"], OTHER_CHOICE)
        self.assertEqual(data["age_group_id"], new_age_group.id)
        self.assertEqual(data["group_id"], new_group.id)
        self.assertEqual(data["group_2_id"], new_group_2.id)

    def test_get_method_not_allowed(self):
        """Test GET method is not allowed."""
        self.authenticate()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_method_only_allowed(self):
        """Test that only PATCH method is allowed."""
        self.authenticate()

        # POST should not be allowed
        response_post = self.client.post(self.url, self.user_payload)
        self.assertEqual(response_post.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT should not be allowed
        response_put = self.client.put(self.url, self.user_payload)
        self.assertEqual(response_put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE should not be allowed
        response_delete = self.client.delete(self.url)
        self.assertEqual(response_delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH should work
        response_patch = self.client.patch(self.url, self.user_payload)
        self.assertEqual(response_patch.status_code, status.HTTP_200_OK)

        # GET should not be allowed
        response_get = self.client.get(self.url)
        self.assertEqual(response_get.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_authenticated_without_citizen_returns_404(self):
        """Authenticated user without a Citizen should get 404."""
        self.authenticate()
        self.issues_citizen.delete()
        response = self.client.patch(self.url, self.user_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("Not found", str(response.data["detail"]))
