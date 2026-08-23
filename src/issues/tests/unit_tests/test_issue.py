from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from authentication.factories import GovernmentWorkerFactory, UserFactory
from authentication.models import GovernmentWorker
from grm.constants import (
    ALERT_CHOICE,
    ANONYMOUS_CHOICE,
    FACILITATOR_CHOICE,
    PHONE_CHOICE,
)
from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
    IssueFactory,
    IssueStatusFactory,
)
from issues.models import IssueStatusChange


@pytest.mark.django_db
class IssueTest(TestCase):
    """
    Tests for the custom methods and properties of the Issue model.
    """

    def setUp(self):
        reset_sequences()
        super().setUp()

    def test_resolution_days_with_resolution_date(self):
        issue = IssueFactory(
            intake_date=timezone.now() - timedelta(days=5),
        )
        issue.resolution_date = timezone.now()
        issue.save()
        self.assertEqual(issue.resolution_days(), 5)

    def test_resolution_days_without_resolution_date(self):
        issue = IssueFactory()
        self.assertIsNone(issue.resolution_days())

    def test_issue_is_created_with_default_contact_medium(self):
        issue = IssueFactory(contact_medium=ANONYMOUS_CHOICE)
        self.assertEqual(issue.contact_medium, ANONYMOUS_CHOICE)

    def test_issue_is_created_with_default_intake_date(self):
        issue = IssueFactory()
        self.assertIsNotNone(issue.intake_date)

    def test_ongoing_issue_default_is_false(self):
        issue = IssueFactory()
        self.assertFalse(issue.ongoing_issue)

    def test_automatic_tracking_code_generation(self):
        issue = IssueFactory()
        self.assertIsNotNone(issue.tracking_code)

    def test_contact_method_is_required_for_channel_alert_medium(self):
        with self.assertRaises(ValidationError):
            IssueFactory(contact_medium=ALERT_CHOICE, contact_method=None)

    def test_valid_issue_saves_correctly(self):
        issue = IssueFactory(
            contact_medium=FACILITATOR_CHOICE, contact_method=PHONE_CHOICE, contact_information="1234567890"
        )
        try:
            issue.full_clean()
            issue.save()
        except ValidationError:
            self.fail("ValidationError was raised on a valid model instance.")

    def test_full_clean_is_called_on_save(self):
        issue = IssueFactory.build(contact_medium=ALERT_CHOICE, contact_method=None)
        with self.assertRaises(ValidationError):
            issue.save()


@pytest.mark.django_db
class TestIssueIsPiuStaff(TestCase):
    """
    Tests for the is_piu_staff method of the Issue model.
    """

    def setUp(self):
        reset_sequences()
        super().setUp()
        self.root_region = AdministrativeRegionFactory()

    def _make_head_worker_with_department(self, region=None):
        """
        Create a GovernmentWorker and make the same user the head of the worker's department.
        Optionally attach a specific administrative region to the worker.
        Returns (worker_user, worker_instance, department)
        """
        if region is None:
            region = AdministrativeRegionFactory(parent=self.root_region)
        # Department and head
        head_user = UserFactory()
        department = IssueDepartmentFactory(head=head_user)
        # Government worker record for the head user
        worker = GovernmentWorker.objects.create(
            user=head_user,
            department=department,
            administrative_region=region,
        )
        return head_user, worker, department

    def _make_category_for_department(self, department):
        # Ensure the category's assigned_department points to the provided department
        dep_level = IssueDepartmentAdministrativeLevelFactory(department=department)
        category = IssueCategoryFactory(assigned_department=dep_level)
        return category

    def test_true_when_user_is_assignee(self):
        issue = IssueFactory(administrative_region=self.root_region)
        GovernmentWorkerFactory(
            user=issue.assignee,
            administrative_region=self.root_region,
        )
        assert issue.is_piu_staff(issue.assignee) is True

    def test_true_when_head_and_category_matches_and_region_is_same(self):
        # Head worker with region R
        head_user, worker, department = self._make_head_worker_with_department()
        # Category assigned to the same department
        category = self._make_category_for_department(department)
        # Issue in same region as worker
        issue = IssueFactory(
            category=category,
            administrative_region=worker.administrative_region,
            assignee=None,
        )
        assert issue.is_piu_staff(head_user) is True

    def test_true_when_head_and_category_matches_and_region_is_descendant(self):
        # Head worker with region parent R
        head_user, worker, department = self._make_head_worker_with_department()
        child_region = AdministrativeRegionFactory(parent=worker.administrative_region)
        category = self._make_category_for_department(department)
        issue = IssueFactory(category=category, administrative_region=child_region, assignee=None)
        assert issue.is_piu_staff(head_user) is True

    def test_false_when_head_and_category_match_but_region_outside_hierarchy(self):
        head_user, worker, department = self._make_head_worker_with_department()
        other_root = AdministrativeRegionFactory(parent=self.root_region)  # different root -> not descendant
        category = self._make_category_for_department(department)
        issue = IssueFactory(category=category, administrative_region=other_root, assignee=None)
        assert issue.is_piu_staff(head_user) is False

    def test_false_when_head_and_region_match_but_category_not_of_department(self):
        head_user, worker, department = self._make_head_worker_with_department()
        # Category assigned to a different department
        other_department = IssueDepartmentFactory()
        category = self._make_category_for_department(other_department)
        issue = IssueFactory(category=category, administrative_region=worker.administrative_region, assignee=None)
        assert issue.is_piu_staff(head_user) is False

    def test_false_when_not_head_even_if_category_and_region_match(self):
        # Create a department whose head is SOMEONE ELSE
        actual_head = UserFactory()
        department = IssueDepartmentFactory(head=actual_head)
        region = AdministrativeRegionFactory(parent=self.root_region)
        # Worker is in department but is not head
        user = UserFactory()
        GovernmentWorker.objects.create(user=user, department=department, administrative_region=region)
        # Category assigned to that department
        category = IssueCategoryFactory(
            assigned_department=IssueDepartmentAdministrativeLevelFactory(department=department)
        )
        issue = IssueFactory(category=category, administrative_region=region, assignee=None)
        assert issue.is_piu_staff(user) is False

    def test_false_when_user_is_not_government_worker(self):
        user = UserFactory()
        issue = IssueFactory(administrative_region=self.root_region)
        assert issue.is_piu_staff(user) is False


@pytest.mark.django_db
class IssueStatusChangeSaveBehaviorTest(TestCase):
    """Tests that Issue.save() correctly creates/closes IssueStatusChange rows."""

    def setUp(self):
        super().setUp()
        self.root_region = AdministrativeRegionFactory()
        self.category = IssueCategoryFactory()

        # Non-terminal statuses
        self.status_open = IssueStatusFactory(final_status=False, rejected_status=False, threshold_days=5)
        self.status_other = IssueStatusFactory(final_status=False, rejected_status=False, threshold_days=3)

        # Terminal status (final) - DB requires threshold_days > 0
        self.status_terminal = IssueStatusFactory(final_status=True, rejected_status=False, threshold_days=1)

    def test_create_issue_with_non_terminal_status_creates_issue_status_change(self):
        """Creating an Issue with a non-terminal status should create an open IssueStatusChange."""
        issue = IssueFactory(
            administrative_region=self.root_region,
            category=self.category,
            status=self.status_open,
            confirmed=True,
        )

        # There should be exactly one open IssueStatusChange for this issue/status
        isc = IssueStatusChange.objects.filter(issue=issue, status=self.status_open).order_by('-entered_at').first()
        assert isc is not None
        assert isc.exited_at is None

    def test_create_issue_with_terminal_status_sets_resolution_date_and_no_isc(self):
        """Creating an Issue with a terminal status should set resolution_date and NOT create an IssueStatusChange."""
        issue = IssueFactory(
            administrative_region=self.root_region,
            category=self.category,
            status=self.status_terminal,
            confirmed=True,
        )

        # Reload from DB to ensure fields set by save() are visible
        issue.refresh_from_db()
        assert issue.resolution_date is not None

        # No IssueStatusChange rows should exist for terminal statuses on create
        assert not IssueStatusChange.objects.filter(issue=issue).exists()

    def test_updating_status_closes_previous_and_creates_new_issue_status_change(self):
        """When an Issue changes status, the previous open ISC is closed and a new ISC is created for the new status."""
        # Create issue with initial non-terminal status -> should create ISC A
        issue = IssueFactory(
            administrative_region=self.root_region,
            category=self.category,
            status=self.status_open,
            confirmed=True,
        )

        isc_a = IssueStatusChange.objects.filter(issue=issue, status=self.status_open).order_by('-entered_at').first()
        assert isc_a is not None
        assert isc_a.exited_at is None

        # Change status to another non-terminal status and save -> should close ISC A and create ISC B
        issue.status = self.status_other
        issue.save()

        # Refresh ISCs
        isc_a.refresh_from_db()
        assert isc_a.exited_at is not None

        isc_b = IssueStatusChange.objects.filter(issue=issue, status=self.status_other).order_by('-entered_at').first()
        assert isc_b is not None
        assert isc_b.exited_at is None

    def test_saving_without_status_change_does_not_create_additional_isc(self):
        """Saving an Issue without changing status should not create extra IssueStatusChange rows."""
        issue = IssueFactory(
            administrative_region=self.root_region,
            category=self.category,
            status=self.status_open,
            confirmed=True,
        )

        initial_count = IssueStatusChange.objects.filter(issue=issue).count()
        # Save without changing status
        issue.description = "Minor edit"
        issue.save()

        final_count = IssueStatusChange.objects.filter(issue=issue).count()
        assert final_count == initial_count
