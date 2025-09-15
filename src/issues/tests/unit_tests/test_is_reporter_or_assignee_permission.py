from django.test import TestCase

from authentication.factories import UserFactory
from grm.utils import reset_sequences
from issues.factories import AdministrativeRegionFactory, IssueFactory
from issues.permissions import IsReporterOrAssigneePermission


class IsReporterOrAssigneePermissionTest(TestCase):
    """Test cases for the custom permission class."""

    def setUp(self):
        """Set up test data."""
        reset_sequences()

        self.reporter_user = UserFactory(username='reporter')
        self.assignee_user = UserFactory(username='assignee')
        self.other_user = UserFactory(username='other')
        self.admin_region = AdministrativeRegionFactory(name="KADJÈRÈ")

        self.issue = IssueFactory(
            administrative_region=self.admin_region,
            reporter=self.reporter_user,
            assignee=self.assignee_user,
        )

        self.permission = IsReporterOrAssigneePermission()

    def test_reporter_has_permission(self):
        """Test that the reporter has permission to access the issue."""
        request = self._create_mock_request(self.reporter_user)
        has_permission = self.permission.has_object_permission(request, None, self.issue)
        self.assertTrue(has_permission)

    def test_assignee_has_permission(self):
        """Test that the assignee has permission to access the issue."""
        request = self._create_mock_request(self.assignee_user)
        has_permission = self.permission.has_object_permission(request, None, self.issue)
        self.assertTrue(has_permission)

    def test_other_user_no_permission(self):
        """Test that other users don't have permission to access the issue."""
        request = self._create_mock_request(self.other_user)
        has_permission = self.permission.has_object_permission(request, None, self.issue)
        self.assertFalse(has_permission)

    def test_reporter_has_permission_with_issue_id(self):
        request = self._create_mock_request(self.reporter_user)
        view = self._create_mock_view(issue_id=self.issue.id)
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)

    def test_assignee_has_permission_with_issue_id(self):
        request = self._create_mock_request(self.assignee_user)
        view = self._create_mock_view(issue_id=self.issue.id)
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)

    def test_other_user_no_permission_with_issue_id(self):
        request = self._create_mock_request(self.other_user)
        view = self._create_mock_view(issue_id=self.issue.id)
        has_permission = self.permission.has_permission(request, view)
        self.assertFalse(has_permission)

    def test_permission_without_issue_id(self):
        request = self._create_mock_request(self.other_user)
        view = self._create_mock_view(issue_id=None)
        has_permission = self.permission.has_permission(request, view)
        self.assertTrue(has_permission)

    def _create_mock_request(self, user):
        class MockRequest:
            def __init__(self, user):
                self.user = user

        return MockRequest(user)

    def _create_mock_view(self, issue_id):
        class MockView:
            def __init__(self, issue_id):
                self.kwargs = {}
                if issue_id is not None:
                    self.kwargs["id"] = issue_id

        return MockView(issue_id)
