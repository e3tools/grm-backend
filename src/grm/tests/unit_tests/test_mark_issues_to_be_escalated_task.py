from datetime import timedelta

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from grm.tasks import mark_issues_to_be_escalated
from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeRegionFactory,
    IssueFactory,
    IssueStatusChangeFactory,
    IssueStatusFactory,
)
from issues.models import IssueStatusChange


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class MarkIssuesToBeEscalatedTaskTest(TestCase):
    def setUp(self):
        self.region = AdministrativeRegionFactory()
        IssueFactory(confirmed=True, escalate_flag=True, administrative_region=self.region)  # issue to ignore
        reset_sequences()

    def _make_issue_with_open_change(self, *, days_in_status: int, threshold: int = 3, **issue_kwargs):
        """
        Helper to create an Issue with a specific number of days in current status.
        Update open IssueStatusChange (exited_at=None) with entered_at in the past accordingly.
        """
        status = IssueStatusFactory(
            threshold_days_to_escalate=threshold,
            final_status=False,
            rejected_status=False,
        )
        issue = IssueFactory(
            status=status, confirmed=True, escalate_flag=False, administrative_region=self.region, **issue_kwargs
        )
        entered_at = timezone.now() - timedelta(days=days_in_status)
        IssueStatusChange.objects.filter(issue=issue, status=status, exited_at=None).update(entered_at=entered_at)
        return issue

    def test_escalates_when_exceeds_threshold(self):
        # Issue has been in current status 5 days, threshold is 3 -> should escalate
        issue = self._make_issue_with_open_change(days_in_status=5, threshold=3)

        result = mark_issues_to_be_escalated()
        issue.refresh_from_db()

        assert result == {"updated_issues": 1}
        assert issue.escalate_flag is True

    def test_does_not_escalate_if_below_or_equal_threshold(self):
        # 2 days in status with threshold 3 -> no escalation
        issue1 = self._make_issue_with_open_change(days_in_status=2, threshold=3)
        # exactly 3 days in status with threshold 3 -> no escalation (strictly greater in task)
        issue2 = self._make_issue_with_open_change(days_in_status=3, threshold=3)

        result = mark_issues_to_be_escalated()
        issue1.refresh_from_db()
        issue2.refresh_from_db()

        assert result == {"updated_issues": 0}
        assert issue1.escalate_flag is False
        assert issue2.escalate_flag is False

    def test_ignores_final_and_rejected_statuses(self):
        # Final status should be ignored even if over threshold
        final_status = IssueStatusFactory(final_status=True, rejected_status=False, threshold_days_to_escalate=2)
        issue_final = IssueFactory(
            status=final_status, confirmed=True, escalate_flag=False, administrative_region=self.region
        )
        IssueStatusChangeFactory(
            issue=issue_final, status=final_status, entered_at=timezone.now() - timedelta(days=10), exited_at=None
        )

        # Rejected status should be ignored even if over threshold
        rej_status = IssueStatusFactory(final_status=False, rejected_status=True, threshold_days_to_escalate=2)
        issue_rej = IssueFactory(
            status=rej_status, confirmed=True, escalate_flag=False, administrative_region=self.region
        )
        IssueStatusChangeFactory(
            issue=issue_rej, status=rej_status, entered_at=timezone.now() - timedelta(days=10), exited_at=None
        )

        result = mark_issues_to_be_escalated()
        issue_final.refresh_from_db()
        issue_rej.refresh_from_db()

        assert result == {"updated_issues": 0}
        assert issue_final.escalate_flag is False
        assert issue_rej.escalate_flag is False

    def test_excludes_issues_without_threshold(self):
        # Status with no threshold_days_to_escalate should be excluded by the task
        status_no_threshold = IssueStatusFactory(threshold_days_to_escalate=None)
        issue = IssueFactory(
            status=status_no_threshold, confirmed=True, escalate_flag=False, administrative_region=self.region
        )
        IssueStatusChange.objects.filter(issue=issue, exited_at=None).update(
            entered_at=timezone.now() - timedelta(days=10), status=status_no_threshold
        )

        result = mark_issues_to_be_escalated()
        issue.refresh_from_db()

        assert result == {"updated_issues": 0}
        assert issue.escalate_flag is False

    def test_mixed_batch_updates_only_eligible_issues(self):
        # Eligible (over threshold)
        eligible = self._make_issue_with_open_change(days_in_status=7, threshold=3)
        # Not eligible (below threshold)
        not_eligible = self._make_issue_with_open_change(days_in_status=1, threshold=3)
        # Excluded because of final status
        final_status = IssueStatusFactory(final_status=True, threshold_days_to_escalate=1)
        excluded_final = IssueFactory(
            status=final_status, confirmed=True, escalate_flag=False, administrative_region=self.region
        )
        IssueStatusChangeFactory(
            issue=excluded_final, status=final_status, entered_at=timezone.now() - timedelta(days=10), exited_at=None
        )

        result = mark_issues_to_be_escalated()

        eligible.refresh_from_db()
        not_eligible.refresh_from_db()
        excluded_final.refresh_from_db()

        assert result == {"updated_issues": 1}
        assert eligible.escalate_flag is True
        assert not_eligible.escalate_flag is False
        assert excluded_final.escalate_flag is False


def _make_issue_with_open_change_fn(days_in_status: int, threshold: int = 3, **issue_kwargs):
    region = AdministrativeRegionFactory()
    status = IssueStatusFactory(
        threshold_days_to_escalate=threshold,
        final_status=False,
        rejected_status=False,
    )
    issue = IssueFactory(
        status=status,
        confirmed=True,
        escalate_flag=False,
        administrative_region=region,
        **issue_kwargs,
    )
    entered_at = timezone.now() - timedelta(days=days_in_status)
    IssueStatusChange.objects.filter(issue=issue, status=status, exited_at=None).update(entered_at=entered_at)
    return issue


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@pytest.mark.parametrize(
    "threshold,days,should_escalate",
    [
        (2, 1, False),  # below
        (2, 2, False),  # equal
        (2, 3, True),  # above
        (5, 7, True),  # another threshold
    ],
)
def test_escalation_thresholds(threshold, days, should_escalate):
    issue = _make_issue_with_open_change_fn(days_in_status=days, threshold=threshold)

    result = mark_issues_to_be_escalated()
    issue.refresh_from_db()

    assert result["updated_issues"] == (1 if should_escalate else 0)
    assert issue.escalate_flag is should_escalate
