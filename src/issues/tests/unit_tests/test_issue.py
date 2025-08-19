from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeLevelFactory,
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
    IssueFactory,
    IssueStatusFactory,
    IssueTypeFactory,
    UserFactory,
)
from issues.models import AdministrativeRegion


@pytest.mark.django_db
class TestIssue(TestCase):
    """
    Tests for the custom methods and properties of the Issue model.
    """

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
        self.department = IssueDepartmentFactory(name="Test Department")
        self.department_admin_level = IssueDepartmentAdministrativeLevelFactory(
            department=self.department, administrative_level=self.administrative_level
        )
        self.category = IssueCategoryFactory(
            name="Test Category",
            assigned_department=self.department_admin_level,
            assigned_appeal_department=self.department_admin_level,
            assigned_escalation_department=self.department_admin_level,
        )
        self.issue_type = IssueTypeFactory(name="Test Issue Type")
        self.status = IssueStatusFactory(name="Test Status")
        self.reporter = UserFactory()
        self.assignee = UserFactory()
        super().setUp()

    def test_resolution_days_with_resolution_date(self):
        issue = IssueFactory(
            intake_date=timezone.now() - timedelta(days=5),
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        issue.resolution_date = timezone.now()
        issue.save()
        self.assertEqual(issue.resolution_days(), 5)

    def test_resolution_days_without_resolution_date(self):
        issue = IssueFactory(
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertIsNone(issue.resolution_days())

    def test_issue_is_created_with_default_contact_medium(self):
        issue = IssueFactory(
            contact_medium="channel-alert",
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertEqual(issue.contact_medium, "channel-alert")

    def test_issue_is_created_with_default_intake_date(self):
        issue = IssueFactory(
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertIsNotNone(issue.intake_date)

    def test_ongoing_issue_default_is_false(self):
        issue = IssueFactory(
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertFalse(issue.ongoing_issue)

    def test_automatic_tracking_code_generation(self):
        issue = IssueFactory(
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertIsNotNone(issue.tracking_code)

    def test_contact_method_is_required_for_non_channel_alert_medium(self):
        with self.assertRaises(ValidationError):
            IssueFactory(
                contact_medium="facilitator",
                contact_method=None,
                administrative_region=self.child_region,
                category=self.category,
                issue_type=self.issue_type,
                status=self.status,
                reporter=self.reporter,
                assignee=self.assignee,
            )

    def test_contact_information_is_valid_for_email_method(self):

        with self.assertRaises(ValidationError):
            IssueFactory(
                contact_method="email",
                contact_information="not_an_email",
                administrative_region=self.child_region,
                category=self.category,
                issue_type=self.issue_type,
                status=self.status,
                reporter=self.reporter,
                assignee=self.assignee,
            )

    def test_contact_information_is_valid_for_non_email_method(self):
        with self.assertRaises(ValidationError):
            IssueFactory(
                contact_method="phone_number",
                contact_information="valid_email@example.com",
                administrative_region=self.child_region,
                category=self.category,
                issue_type=self.issue_type,
                status=self.status,
                reporter=self.reporter,
                assignee=self.assignee,
            )

    def test_valid_issue_saves_correctly(self):
        issue = IssueFactory(
            contact_medium="facilitator",
            contact_method="phone_number",
            contact_information="1234567890",
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        try:
            issue.full_clean()
            issue.save()
        except ValidationError:
            self.fail("ValidationError was raised on a valid model instance.")

    def test_full_clean_is_called_on_save(self):
        issue = IssueFactory.build(
            contact_medium="facilitator",
            contact_method=None,
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        with self.assertRaises(ValidationError):
            issue.save()
