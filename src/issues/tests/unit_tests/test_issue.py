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
)


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
