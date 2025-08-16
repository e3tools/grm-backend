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
    def setUpClass(cls):
        """
        Setup de la clase, se ejecuta una sola vez.
        Crea las dependencias de datos que serán compartidas por todos los tests.
        """
        super().setUpClass()

        # Reset database sequences at the start of setUpClass to prevent primary key
        # conflicts with pre-existing data from other test classes.
        reset_sequences()

        # Ensure a clean slate by deleting any pre-existing regions with no parent.
        # This addresses the "Only one AdministrativeRegion can have no parent" error.
        AdministrativeRegion.objects.filter(parent__isnull=True).delete()

        # Create all necessary factory objects for the payload
        cls.administrative_level = AdministrativeLevelFactory(name="Country")
        cls.root_region = AdministrativeRegionFactory(
            name="Root Region",
            administrative_level=cls.administrative_level,
            parent=None,
        )
        cls.child_region = AdministrativeRegionFactory(
            name="Child Region",
            administrative_level=cls.administrative_level,
            parent=cls.root_region,
        )
        cls.reporter_user = UserFactory()
        cls.assignee_user = UserFactory()
        cls.department = IssueDepartmentFactory(name="Test Department")
        cls.department_admin_level = IssueDepartmentAdministrativeLevelFactory(
            department=cls.department, administrative_level=cls.administrative_level
        )
        cls.issue_category = IssueCategoryFactory(
            name="Test Category",
            assigned_department=cls.department_admin_level,
            assigned_appeal_department=cls.department_admin_level,
            assigned_escalation_department=cls.department_admin_level,
        )
        cls.issue_type = IssueTypeFactory(name="Test Issue Type")
        cls.initial_status = IssueStatusFactory()
        cls.component = ComponentFactory()
        cls.sub_component = SubComponentFactory()
        cls.age_group = CitizenAgeGroupFactory()
        cls.group_one = CitizenGroupFactory()
        cls.group_two = CitizenGroupFactory()
        cls.citizen = CitizenFactory(age_group=cls.age_group, group=cls.group_one, group_2=cls.group_two)

    def setUp(self):
        # Reset database sequences before each test to prevent IntegrityError on primary keys
        reset_sequences()
        super().setUp()

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
