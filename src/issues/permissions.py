from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from issues.models import Issue


class IsReporterOrAssigneePermission(BasePermission):
    """
    Custom permission to only allow reporters or assignees to view an issue.

    This permission checks if the requesting user is either:
    - The reporter of the issue
    - The assignee of the issue
    """

    def has_object_permission(self, request, view, obj):
        """
        Check if the user has permission to access this specific issue.

        Args:
            request: HTTP request object
            view: The view being accessed
            obj: The Issue object being accessed

        Returns:
            bool: True if user is reporter or assignee, False otherwise
        """
        # Allow access if user is the reporter or assignee
        return request.user == obj.reporter or request.user == obj.assignee

    def has_permission(self, request, view):
        """
        Check if the user has permission to access the view based on the issue context.

        This method is evaluated before accessing the queryset or any specific object.
        It ensures that the requesting user is either the reporter or the assignee of
        the issue referenced in the URL (via the "id" parameter).

        Args:
            request: HTTP request object
            view: The view being accessed

        Returns:
            bool: True if user is the reporter or assignee of the issue, False otherwise
        """
        issue_id = view.kwargs.get("id")
        if not issue_id:
            return True  # No issue context available, allow access
        issue = get_object_or_404(Issue, id=issue_id)
        if not issue:
            return False
        return request.user == issue.reporter or request.user == issue.assignee
