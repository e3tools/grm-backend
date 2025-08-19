import pytest
from django.urls import reverse  # Import reverse to use named URLs in tests
from rest_framework import status
from rest_framework.test import APITestCase  # Use APITestCase for DRF views

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
    IssueTypeFactory,
    SubComponentFactory,
    UserFactory,
)
from issues.models import AdministrativeRegion, Issue


@pytest.mark.django_db
class TestIssueCreateAPIView(APITestCase):
    """
    Tests for the IssueCreateAPIView.
    """

    @classmethod
    def setUp(self):
        reset_sequences()

        AdministrativeRegion.objects.filter(parent__isnull=True).delete()
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
        self.initial_status = IssueStatusFactory()
        self.component = ComponentFactory()
        self.sub_component = SubComponentFactory()
        self.age_group = CitizenAgeGroupFactory()
        self.group_one = CitizenGroupFactory()
        self.group_two = CitizenGroupFactory()
        self.citizen = CitizenFactory(age_group=self.age_group, group=self.group_one, group_2=self.group_two)

    def test_create_issue_with_valid_data(self):
        """
        Tests that an issue can be created with valid data.
        """
        self.client.force_authenticate(user=self.reporter_user)

        data = {
            "title": "Test Issue",
            "description": "This is a test issue.",
            "status": self.initial_status.pk,
            "category": self.issue_category.pk,
            "issue_type": self.issue_type.pk,
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
            "contact_medium": "channel-alert",
            "contact_method": None,
            "contact_information": "aa",
            "ongoing_issue": True,
            "tracking_code": "TRACK123",
        }

        # Use reverse with the app namespace
        url = reverse("issues:create-issue")
        response = self.client.post(url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Issue.objects.count(), 1)
        created_issue = Issue.objects.get()
        self.assertEqual(created_issue.title, "Test Issue")
        self.assertEqual(created_issue.reporter, self.reporter_user)
        self.assertEqual(created_issue.administrative_region, self.child_region)

    def test_create_issue_with_invalid_data(self):
        """
        Tests that an issue cannot be created with invalid data.
        """
        self.client.force_authenticate(user=self.reporter_user)

        data = {
            # Missing required fields like 'title'
            "description": "This is a test issue.",
        }

        # Use reverse with the app namespace
        url = reverse("issues:create-issue")
        response = self.client.post(url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Issue.objects.count(), 0)

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
