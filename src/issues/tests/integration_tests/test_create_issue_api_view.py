import pytest
from django.urls import reverse  # Import reverse to use named URLs in tests
from rest_framework import status
from rest_framework.test import APITestCase  # Use APITestCase for DRF views

from dashboard.grm.constants import CHOICE_FACILITATOR
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
class TestIssueCreateAPIView(APITestCase):
    """
    Tests for the IssueCreateAPIView.
    """

    def setUp(self):
        reset_sequences()
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

        url = reverse("issues:create-issue")
        response = self.client.post(url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Issue.objects.count(), 1)
        created_issue = Issue.objects.get()
        self.assertEqual(created_issue.title, "Test Issue")
        self.assertEqual(created_issue.reporter, self.reporter_user)
        self.assertEqual(created_issue.administrative_region, self.child_region)

    def test_create_issue_without_authentication(self):
        """
        Tests that an issue cannot be created without authentication.
        """
        data = {
            "title": "Test Issue",
            "description": "This is a test issue.",
            "intake_date": "2023-01-01T10:00:00Z",
            "contact_medium": "channel-alert",
            "issue_type": self.issue_type.pk,
            "category": self.issue_category.pk,
            "administrative_region": self.child_region.pk,
        }

        # Use reverse with the app namespace
        url = reverse("issues:create-issue")
        response = self.client.post(url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Issue.objects.count(), 0)

    def test_create_issue_with_missing_required_field(self):
        self.client.force_authenticate(user=self.reporter_user)

        test_cases = [
            {"expected_error_field": "title"},
            {"expected_error_field": "description"},
            {"expected_error_field": "issue_location"},
            {"expected_error_field": "contact_medium"},
            {"expected_error_field": "intake_date"},
            {"expected_error_field": "issue_type"},
            {"expected_error_field": "issue_sub_type"},
            {"expected_error_field": "tracking_code"},
        ]
        url = reverse("issues:create-issue")

        for case in test_cases:
            data = self.__get_valid_data()
            del data[case["expected_error_field"]]

            with self.subTest(msg=f"Testing missing field: {case['expected_error_field']}"):
                response = self.client.post(url, data=data, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(case["expected_error_field"], response.data['errors'])
                self.assertEqual(Issue.objects.count(), 0)

    def __get_valid_data(self):
        return {
            "title": "Test Issue",
            "description": "This is a test issue.",
            "status": self.initial_status.pk,
            "category": self.issue_category.pk,
            "issue_type": self.issue_type.pk,
            "issue_sub_type": self.issue_sub_type.pk,
            "issue_location": self.child_region.pk,
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
            "contact_medium": CHOICE_FACILITATOR,
            "contact_method": None,
            "contact_information": "aa",
            "ongoing_issue": True,
            "tracking_code": "TRACK123",
        }
