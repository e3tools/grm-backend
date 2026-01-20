"""
Permission helper functions for GRM dashboard views.

This module centralizes permission checks related to Issues so views remain clean
and easier to test. If more complex permission logic is needed in the future,
consider moving to Django permissions or a dedicated policy layer.
"""


def user_can_access_issue(user, issue):
    """
    Check if the user can access (read) an issue.

    Rules:
    - If issue is unconfirmed (confirmed=False): Only the reporter
    - If issue is confirmed (confirmed=True):
        * GRM Manager: Can access all issues
        * Case Manager: Can access if the user is PIU staff for the issue

    Args:
        user: User object
        issue: Issue object

    Returns:
        bool: True if the user can access the issue
    """
    if issue.confirmed:
        if getattr(user, "grm_manager", False):
            return True

        elif hasattr(user, "governmentworker"):
            return issue.is_piu_staff(user)
    else:
        return reporter_can_access_issue(user, issue)

    return False


def reporter_can_access_issue(user, issue):
    """
    Check if the user is a reporter of the issue.

    Args:
        user: User object
        issue: Issue object

    Returns:
        bool: True if the user is a reporter of the issue
    """
    return getattr(issue, "reporter_id", None) == getattr(user, "id", None)
