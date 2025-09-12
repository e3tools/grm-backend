from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from grm.constants import (
    ALERT_CHOICE,
    CONTACT_INFO_EMAIL_ERROR_MESSAGE,
    CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE,
    CONTACT_MEDIUM_ERROR_MESSAGE,
    FACILITATOR_CHOICE,
    ISSUE_CREATE_ERROR_MESSAGE,
    ISSUE_CREATE_SUCCESS_MESSAGE,
)
from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeLevelFactory,
    AdministrativeRegionFactory,
    CitizenAgeGroupFactory,
    CitizenFactory,
    CitizenGroupFactory,
    ComponentFactory,
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
    IssueStatusFactory,
    IssueSubTypeFactory,
    IssueTypeFactory,
    SubComponentFactory,
    UserFactory,
)
from issues.models import Issue


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class IssueCreateAPIViewTest(APITestCase):
    """
    Tests for the IssueCreateAPIView.
    """

    def setUp(self):
        reset_sequences()
        self.url = reverse("issues:create-issue")
        self.administrative_level = AdministrativeLevelFactory(name="Country")
        self.root_region = AdministrativeRegionFactory(
            name="Root Region",
            administrative_level=self.administrative_level,
            parent=None,
        )
        self.child_region = AdministrativeRegionFactory(
            name="Child Region",
            administrative_level=self.administrative_level,
            parent=self.root_region,
        )
        self.reporter_user = UserFactory()
        self.assignee_user = UserFactory()
        self.department = IssueDepartmentFactory(name="Test Department")
        self.department_admin_level = IssueDepartmentAdministrativeLevelFactory(
            department=self.department, administrative_level=self.administrative_level
        )
        self.issue_category = IssueCategoryFactory(
            name="Test Category",
            assigned_department=self.department_admin_level,
            assigned_appeal_department=self.department_admin_level,
            assigned_escalation_department=self.department_admin_level,
        )
        self.issue_type = IssueTypeFactory(name="Test Issue Type")
        self.issue_sub_type = IssueSubTypeFactory(name="Test Issue SubType")

        self.initial_status = IssueStatusFactory()
        self.component = ComponentFactory()
        self.sub_component = SubComponentFactory()
        self.age_group = CitizenAgeGroupFactory()
        self.group_one = CitizenGroupFactory()
        self.group_two = CitizenGroupFactory()
        self.citizen = CitizenFactory(age_group=self.age_group, group=self.group_one, group_2=self.group_two)

    def test_create_issue_with_valid_data(self):
        self.client.force_authenticate(user=self.reporter_user)

        data = self.__get_valid_data()

        response = self.client.post(self.url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], ISSUE_CREATE_SUCCESS_MESSAGE)
        self.assertEqual(Issue.objects.count(), 1)
        created_issue = Issue.objects.get()
        self.assertEqual(created_issue.description, "This is a test issue.")
        self.assertEqual(created_issue.reporter, self.reporter_user)
        self.assertEqual(created_issue.administrative_region, self.child_region)

    def test_create_issue_without_authentication(self):
        """
        Tests that an issue cannot be created without authentication.
        """
        data = {
            "description": "This is a test issue.",
            "intake_date": "2023-01-01T10:00:00Z",
            "contact_medium": "channel-alert",
            "issue_type": self.issue_type.pk,
            "category": self.issue_category.pk,
            "administrative_region": self.child_region.pk,
        }

        response = self.client.post(self.url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Issue.objects.count(), 0)

    def test_create_issue_with_missing_required_field(self):
        self.client.force_authenticate(user=self.reporter_user)

        test_cases = [
            {"expected_error_field": "description"},
            {"expected_error_field": "contact_medium"},
            {"expected_error_field": "intake_date"},
            {"expected_error_field": "issue_type"},
            {"expected_error_field": "issue_sub_type"},
            {"expected_error_field": "tracking_code"},
        ]

        for case in test_cases:
            data = self.__get_valid_data()
            del data[case["expected_error_field"]]

            with self.subTest(msg=f"Testing missing field: {case['expected_error_field']}"):
                response = self.client.post(self.url, data=data, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(case["expected_error_field"], response.data['errors'])
                self.assertEqual(Issue.objects.count(), 0)

    def test_validation_contact_medium_channel_alert_requires_contact_method(self):
        """Test that contact_medium 'channel-alert' requires contact_method."""
        self.client.force_authenticate(user=self.reporter_user)
        data = self.__get_valid_data()
        data['contact_medium'] = ALERT_CHOICE

        response = self.client.post(self.url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error = {"contact_method": [CONTACT_MEDIUM_ERROR_MESSAGE]}
        self.assertEqual(response.data['errors'], error)
        self.assertEqual(Issue.objects.count(), 0)

    def test_validation_contact_medium_channel_alert_with_contact_method_success(self):
        """Test that contact_medium 'channel-alert' with contact_method passes validation."""
        self.client.force_authenticate(user=self.reporter_user)
        data = self.__get_valid_data()
        data['contact_medium'] = ALERT_CHOICE
        data['contact_method'] = 'email'
        data['contact_information'] = 'test@example.com'

        response = self.client.post(self.url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Issue.objects.count(), 1)
        created_issue = Issue.objects.get()
        self.assertEqual(created_issue.description, "This is a test issue.")

    def test_validation_email_contact_method_with_valid_email(self):
        """Test that email contact_method with valid email passes validation."""
        self.client.force_authenticate(user=self.reporter_user)
        data = self.__get_valid_data()
        data['contact_method'] = 'email'
        data['contact_information'] = 'valid.email@example.com'

        response = self.client.post(self.url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Issue.objects.count(), 1)
        created_issue = Issue.objects.get()
        self.assertEqual(created_issue.description, "This is a test issue.")

    def test_validation_email_contact_method_with_invalid_email(self):
        """Test that email contact_method with invalid email fails validation."""

        self.client.force_authenticate(user=self.reporter_user)
        data = self.__get_valid_data()
        data['contact_method'] = 'email'
        data['contact_information'] = 'invalid-email'

        response = self.client.post(self.url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data['errors']['contact_information'][0]), CONTACT_INFO_EMAIL_ERROR_MESSAGE)
        self.assertEqual(Issue.objects.count(), 0)

    def test_validation_no_email_contact_method_with_email_fails(self):
        """Test that phone contact_method with email format fails validation."""

        self.client.force_authenticate(user=self.reporter_user)
        data = self.__get_valid_data()
        data['contact_method'] = 'phone_number'
        data['contact_information'] = 'test@example.com'

        response = self.client.post(self.url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data['errors']['contact_information'][0]), CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE)
        self.assertEqual(Issue.objects.count(), 0)

    def test_validation_no_email_contact_method_with_valid_phone(self):
        """Test that whatsapp contact_method with valid phone number passes."""
        self.client.force_authenticate(user=self.reporter_user)
        data = self.__get_valid_data()
        data['contact_method'] = 'whatsapp'
        data['contact_information'] = '+1234567890'  # Non-email format

        response = self.client.post(self.url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Issue.objects.count(), 1)
        created_issue = Issue.objects.get()
        self.assertEqual(created_issue.description, "This is a test issue.")

    def test_validation_no_contact_method_no_validation_required(self):
        """Test that when contact_method is not set, contact validation is skipped."""
        self.client.force_authenticate(user=self.reporter_user)
        data = self.__get_valid_data()
        data['contact_information'] = 'any-string-here'
        # contact_method is not set

        response = self.client.post(self.url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Issue.objects.count(), 1)
        created_issue = Issue.objects.get()
        self.assertEqual(created_issue.description, "This is a test issue.")

    def test_empty_field_validation(self):
        """Test registration with empty fields."""
        self.client.force_authenticate(user=self.reporter_user)
        data = self.__get_valid_data()
        expected_fields = [
            'description',
            'category',
            'issue_type',
            'administrative_region',
            'reporter',
            'citizen',
            'contact_medium',
            'ongoing_issue',
            'tracking_code',
            'intake_date',
            'issue_sub_type',
        ]
        for field in expected_fields:
            data[field] = ''

        response = self.client.post(self.url, data, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'errors' in response.data

        # All fields should have validation errors
        for field in expected_fields:
            assert field in response.data['errors']

    def test_internal_server_error(self):
        """Test internal server error response."""
        self.client.force_authenticate(user=self.reporter_user)
        data = self.__get_valid_data()
        with patch("issues.views.IssueCreateAPIView.get_serializer", side_effect=RuntimeError("boom")):
            response = self.client.post(self.url, data, format='json')
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data['message'] == ISSUE_CREATE_ERROR_MESSAGE

    def __get_valid_data(self):
        return {
            "description": "This is a test issue.",
            "status": self.initial_status.pk,
            "category": self.issue_category.pk,
            "issue_type": self.issue_type.pk,
            "issue_sub_type": self.issue_sub_type.pk,
            "intake_date": "2011-10-05T14:48:00.000Z",
            "administrative_region": self.child_region.pk,
            "reporter": self.reporter_user.pk,
            "assignee": self.assignee_user.pk,
            "citizen": {
                "name": "Test Citizen",
                "type": "organization_behalf_someone",
                "age_group": self.age_group.pk,
                "group": self.group_one.pk,
                "group_2": self.group_two.pk,
            },
            "component": self.component.pk,
            "sub_component": self.sub_component.pk,
            "contact_medium": FACILITATOR_CHOICE,
            "contact_method": None,
            "contact_information": "123456",
            "ongoing_issue": True,
            "tracking_code": "TRACK123",
            "location_description": "This is a test location.",
        }
