import pytest
from django.test import TestCase, override_settings

from grm.tasks import reassign_issues_to_appeal
from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
    IssueFactory,
    UserFactory,
)


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ReassignIssuesToAppealTaskTest(TestCase):
    def setUp(self):
        reset_sequences()

    def test_reassign_with_head_available(self):
        """Test that issues are reassigned when head is available."""
        # Create head user
        head = UserFactory()

        # Create department with head
        department = IssueDepartmentFactory(head=head)
        appeal_level = IssueDepartmentAdministrativeLevelFactory(department=department)
        category = IssueCategoryFactory(assigned_appeal_department=appeal_level)

        # Create issue eligible for reassignment
        issue = IssueFactory(category=category, confirmed=True, appeal_status=True)

        result = reassign_issues_to_appeal()

        issue.refresh_from_db()

        self.assertEqual(result["updated_issues"], 1)
        self.assertEqual(issue.assignee, head)
        self.assertFalse(issue.appeal_status)
        self.assertEqual('', issue.appeal_reason)
        self.assertIn(issue.id, result["issues_updated"])

    def test_reassign_multiple_issues_with_one_not_applicable(self):
        """Test that multiple issues are reassigned while one issue that does not apply is ignored."""
        # Create head user
        head = UserFactory()

        # Create department with head
        department = IssueDepartmentFactory(head=head)
        appeal_level = IssueDepartmentAdministrativeLevelFactory(department=department)
        category = IssueCategoryFactory(assigned_appeal_department=appeal_level)
        region = AdministrativeRegionFactory()

        # Create 3 issues eligible for reassignment
        issues = [
            IssueFactory(category=category, confirmed=True, appeal_status=True, administrative_region=region)
            for _ in range(3)
        ]

        # Create 1 issue not eligible (e.g., appeal_status=False)
        ineligible_issue = IssueFactory(
            category=category, confirmed=True, appeal_status=False, administrative_region=region
        )

        # Run the task
        result = reassign_issues_to_appeal()

        # Refresh issues from DB
        for issue in issues:
            issue.refresh_from_db()

        ineligible_issue.refresh_from_db()

        # Assertions
        self.assertEqual(result["updated_issues"], 3)
        self.assertEqual(set(result["issues_updated"]), {issue.id for issue in issues})
        self.assertNotIn(ineligible_issue.id, result["issues_updated"])

        for issue in issues:
            self.assertEqual(issue.assignee, head)
            self.assertFalse(issue.appeal_status, False)  # appeal_status should be reset

        # Ineligible issue must remain unchanged
        self.assertIsNotNone(ineligible_issue.assignee)  # keeps original assignee
        self.assertFalse(ineligible_issue.appeal_status)  # already False

    def test_reassign_with_no_head(self):
        """Test that issues are not reassigned when head is missing."""
        department = IssueDepartmentFactory(head=None)
        appeal_level = IssueDepartmentAdministrativeLevelFactory(department=department)
        category = IssueCategoryFactory(assigned_appeal_department=appeal_level)

        issue = IssueFactory(category=category, confirmed=True, appeal_status=True)
        previous_assignee = issue.assignee

        result = reassign_issues_to_appeal()

        issue.refresh_from_db()

        self.assertEqual(result["updated_issues"], 0)
        self.assertEqual(issue.assignee, previous_assignee)
        self.assertTrue(issue.appeal_status)
        self.assertIn(issue.id, result["appeal_is_not_available"])

    def test_no_issues_to_reassign(self):
        """Test when there are no issues eligible for reassignment."""
        # Create issue that does not meet the filter
        IssueFactory(confirmed=False, appeal_status=True)

        result = reassign_issues_to_appeal()

        self.assertEqual(result["updated_issues"], 0)
        self.assertEqual(result["issues_updated"], [])
        self.assertEqual(result["appeal_is_not_available"], [])

    def test_exception_handling(self):
        """
        Test that issues go to appeal_is_not_available if an exception occurs
        during reassignment.
        """
        issue = IssueFactory(confirmed=True, appeal_status=True, category=None)

        # Raise an exception when accessing category.assigned_appeal_department
        with pytest.raises(Exception):
            # sanity check: this raises the exception
            _ = issue.category.assigned_appeal_department
        # But the exception must be caught in the task
        result = reassign_issues_to_appeal()

        self.assertEqual(result["updated_issues"], 0)
        self.assertIn(issue.id, result["appeal_is_not_available"])
        self.assertEqual(result["issues_updated"], [])
