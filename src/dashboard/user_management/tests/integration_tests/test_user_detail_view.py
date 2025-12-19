from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from authentication.factories import UserFactory
from authentication.models import Facilitator, GovernmentWorker
from dashboard.constants import LABEL_ACTIVE, LABEL_INACTIVE, LABEL_LOW_ACTIVITY
from dashboard.user_management.constants import (
    CASE_MANAGER_CHOICE,
    CASE_MANAGER_DISPLAY,
    FACILITATOR_CHOICE,
    FACILITATOR_DISPLAY,
    GRM_MANAGER_CHOICE,
    GRM_MANAGER_DISPLAY,
)
from grm.tests.base import DashboardTestCase
from issues.factories import IssueDepartmentFactory, IssueFactory, IssueStatusFactory


class UserDetailViewTest(DashboardTestCase):
    """Tests for UserDetailView"""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.department = IssueDepartmentFactory()

        # Create test users
        self.grm_manager_user = UserFactory(grm_manager=True)

        self.case_manager_user = UserFactory()
        GovernmentWorker.objects.create(
            user=self.case_manager_user,
            department=self.department,
            administrative_region=self.root_region,
        )

        self.facilitator_user = UserFactory()
        Facilitator.objects.create(
            user=self.facilitator_user,
            administrative_region=self.root_region,
            village_secretary=True,
        )

        # Create issue statuses
        self.status_open = IssueStatusFactory(open_status=True, final_status=False, rejected_status=False)
        self.status_resolved = IssueStatusFactory(final_status=True, open_status=False, rejected_status=False)
        self.status_rejected = IssueStatusFactory(rejected_status=True, open_status=False, final_status=False)

    def test_access_granted_for_grm_manager(self):
        """GRM Manager can view user details"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.grm_manager_user.id})
        resp = self.get(url, user=self.manager)
        assert resp.status_code == 200
        assert "user_management/profile.html" in [t.name for t in resp.templates]

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager cannot view user details"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.grm_manager_user.id})
        resp = self.get(url, user=self.normal_user)
        assert resp.status_code == 403

    def test_grm_manager_role_info(self):
        """Should display correct role info for GRM Manager"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.grm_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["user_type"] == GRM_MANAGER_CHOICE
        assert ctx["role_info"]["type_display"] == GRM_MANAGER_DISPLAY
        assert ctx["role_info"]["badge_color"] == 'badge-secondary'

    def test_case_manager_role_info(self):
        """Should display correct role info for Case Manager"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["user_type"] == CASE_MANAGER_CHOICE
        assert ctx["role_info"]["type_display"] == CASE_MANAGER_DISPLAY
        assert ctx["role_info"]["department"] == self.department.name
        assert (
            ctx["role_info"]["administrative_region"]
            == self.case_manager_user.governmentworker.administrative_region.hierarchical_name
        )
        assert ctx["role_info"]["badge_color"] == 'badge-blue'

    def test_case_manager_department_head_indicator(self):
        """Should indicate if Case Manager is department head"""
        self.department.head = self.case_manager_user
        self.department.save()

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["role_info"]["is_department_head"] is True

    def test_facilitator_role_info(self):
        """Should display correct role info for Facilitator"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.facilitator_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert ctx["user_type"] == FACILITATOR_CHOICE
        assert ctx["role_info"]["type_display"] == FACILITATOR_DISPLAY
        assert ctx["role_info"]["village_secretary"] is True
        assert (
            ctx["role_info"]["administrative_region"]
            == self.facilitator_user.facilitator.administrative_region.hierarchical_name
        )
        assert ctx["role_info"]["badge_color"] == 'badge-purple'

    def test_password_confirm_form_present(self):
        """Password confirm form should be in context"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.grm_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)
        assert "password_confirm_form" in ctx

    def test_activity_stats_present_in_context(self):
        """Activity statistics should be present in context"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        assert "activity_stats" in ctx
        stats = ctx["activity_stats"]

        # Verify all required keys are present
        assert "assigned_issues" in stats
        assert "open_issues" in stats
        assert "resolved_issues" in stats
        assert "rejected_issues" in stats
        assert "resolution_rate" in stats
        assert "last_activity_display" in stats
        assert "last_activity_days" in stats
        assert "activity_level" in stats

    def test_assigned_issues_count(self):
        """Should correctly count assigned issues"""
        # Create confirmed issues
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_open,
            administrative_region=self.root_region,
        )
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_resolved,
            administrative_region=self.root_region,
        )
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_rejected,
            administrative_region=self.root_region,
        )

        # Create unconfirmed issue (should not count)
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=False,
            status=self.status_open,
            administrative_region=self.root_region,
        )

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        assert ctx["activity_stats"]["assigned_issues"] == 3

    def test_open_issues_count(self):
        """Should correctly count open issues"""
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_open,
            administrative_region=self.root_region,
        )
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_open,
            administrative_region=self.root_region,
        )
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_resolved,
            administrative_region=self.root_region,
        )

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        assert ctx["activity_stats"]["open_issues"] == 2

    def test_resolved_issues_count(self):
        """Should correctly count resolved issues (final_status=True)"""
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_resolved,
            administrative_region=self.root_region,
        )
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_resolved,
            administrative_region=self.root_region,
        )
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_open,
            administrative_region=self.root_region,
        )

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        assert ctx["activity_stats"]["resolved_issues"] == 2

    def test_rejected_issues_count(self):
        """Should correctly count rejected issues (rejected_status=True)"""
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_rejected,
            administrative_region=self.root_region,
        )
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_rejected,
            administrative_region=self.root_region,
        )
        IssueFactory(
            assignee=self.case_manager_user,
            confirmed=True,
            status=self.status_resolved,
            administrative_region=self.root_region,
        )

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        assert ctx["activity_stats"]["rejected_issues"] == 2

    def test_resolution_rate_calculation(self):
        """Should correctly calculate resolution rate"""
        # Create 10 issues: 6 resolved, 2 rejected, 2 open
        for _ in range(6):
            IssueFactory(
                assignee=self.case_manager_user,
                confirmed=True,
                status=self.status_resolved,
                administrative_region=self.root_region,
            )
        for _ in range(2):
            IssueFactory(
                assignee=self.case_manager_user,
                confirmed=True,
                status=self.status_rejected,
                administrative_region=self.root_region,
            )
        for _ in range(2):
            IssueFactory(
                assignee=self.case_manager_user,
                confirmed=True,
                status=self.status_open,
                administrative_region=self.root_region,
            )

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        # Resolution rate should be (6 + 2) / 10 * 100 = 80%
        assert ctx["activity_stats"]["resolution_rate"] == 80.0

    def test_resolution_rate_none_when_no_assigned_issues(self):
        """Resolution rate should be None when user has no assigned issues"""
        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        assert ctx["activity_stats"]["resolution_rate"] is None

    def test_activity_level_active(self):
        """Should show active status for users active in last 7 days"""
        # Set last activity to 3 days ago
        self.case_manager_user.last_activity = timezone.now() - timedelta(days=3)
        self.case_manager_user.save()

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        activity_level = ctx["activity_stats"]["activity_level"]
        assert activity_level["label"] == LABEL_ACTIVE
        assert activity_level["badge_color"] == "badge-primary"

    def test_activity_level_low_activity(self):
        """Should show low activity for users active 7-20 days ago"""
        # Set last activity to 15 days ago
        self.case_manager_user.last_activity = timezone.now() - timedelta(days=15)
        self.case_manager_user.save()

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        activity_level = ctx["activity_stats"]["activity_level"]
        assert activity_level["label"] == LABEL_LOW_ACTIVITY
        assert activity_level["badge_color"] == "badge-warning"

    def test_activity_level_inactive(self):
        """Should show inactive for users not active in 20+ days"""
        # Set last activity to 30 days ago
        self.case_manager_user.last_activity = timezone.now() - timedelta(days=30)
        self.case_manager_user.save()

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        activity_level = ctx["activity_stats"]["activity_level"]
        assert activity_level["label"] == LABEL_INACTIVE
        assert activity_level["badge_color"] == "badge-secondary"

    def test_activity_level_never_active(self):
        """Should show inactive for users who never logged in"""
        self.case_manager_user.last_activity = None
        self.case_manager_user.save()

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        activity_level = ctx["activity_stats"]["activity_level"]
        assert activity_level["label"] == LABEL_INACTIVE
        assert ctx["activity_stats"]["last_activity_display"] == "Never"

    def test_last_activity_display_today(self):
        """Should display 'Today' for today's activity"""
        self.case_manager_user.last_activity = timezone.now()
        self.case_manager_user.save()

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        assert ctx["activity_stats"]["last_activity_display"] == "Today"

    def test_last_activity_display_yesterday(self):
        """Should display '1 day ago' for yesterday's activity"""
        self.case_manager_user.last_activity = timezone.now() - timedelta(days=1)
        self.case_manager_user.save()

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        assert ctx["activity_stats"]["last_activity_display"] == "1 day ago"

    def test_last_activity_display_multiple_days(self):
        """Should display 'X days ago' for multiple days"""
        self.case_manager_user.last_activity = timezone.now() - timedelta(days=5)
        self.case_manager_user.save()

        url = reverse("dashboard:user_management:detail", kwargs={"pk": self.case_manager_user.id})
        resp = self.get(url, user=self.manager)
        ctx = self.get_context(resp)

        assert "5 days ago" in ctx["activity_stats"]["last_activity_display"]
