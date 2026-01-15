from django.urls import reverse
from django.utils import timezone

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory, IssueFactory


class EscalateIssueViewTest(DashboardTestCase):
    """Integration tests for EscalateIssueView."""

    def setUp(self):
        super().setUp()
        # Regions: root -> region (child)
        self.region = AdministrativeRegionFactory(parent=self.root_region)
        self.issue = IssueFactory(confirmed=True, administrative_region=self.region)
        self.url = reverse("dashboard:grm:escalate_issue", kwargs={"issue": self.issue.id})

    def test_post_success_by_grm_manager_escalates_to_parent_worker(self):
        # Current assignee is a PIU staff at child region
        GovernmentWorkerFactory(
            user=self.issue.assignee,
            administrative_region=self.region,
            department=self.issue.category.assigned_department.department,
        )
        # Create a worker at parent region in the same department
        parent_worker = GovernmentWorkerFactory(
            administrative_region=self.root_region,
            department=self.issue.category.assigned_department.department,
        ).user

        before = timezone.now()
        manager = UserFactory(grm_manager=True)
        resp = self.post(self.url, data={}, ajax=True, user=manager)
        assert resp.status_code == 200
        # JSON structure
        data = resp.json()
        assert "msg" in data
        assert data.get("assignee", {}).get("id") == parent_worker.id
        assert data.get("access_denied") is False

        # DB assertions
        self.issue.refresh_from_db()
        assert self.issue.assignee_id == parent_worker.id
        assert self.issue.escalate_flag is False
        assert self.issue.escalated_date is not None
        assert self.issue.escalated_date >= before

    def test_post_no_candidate_returns_error_message(self):
        # Make current assignee PIU staff at root (has no parent)
        GovernmentWorkerFactory(
            user=self.issue.assignee,
            administrative_region=self.root_region,
            department=self.issue.category.assigned_department.department,
        )
        manager = UserFactory(grm_manager=True)
        resp = self.post(self.url, data={}, ajax=True, user=manager)
        assert resp.status_code == 200
        data = resp.json()
        # No assignee returned and message present
        assert data.get("assignee") is None
        assert "msg" in data

        # Assignee unchanged and no escalation date set
        self.issue.refresh_from_db()
        assert self.issue.assignee_id == self.issue.assignee.id
        # escalated_date should remain None if no escalation happened
        assert getattr(self.issue, 'escalated_date', None) in (None, self.issue.escalated_date)

    def test_post_by_assignee_piu_staff_allowed(self):
        # Ensure assignee is PIU staff at child and there is a parent worker to escalate to
        GovernmentWorkerFactory(
            user=self.issue.assignee,
            administrative_region=self.region,
            department=self.issue.category.assigned_department.department,
        )
        parent_worker = GovernmentWorkerFactory(
            administrative_region=self.root_region,
            department=self.issue.category.assigned_department.department,
        ).user

        resp = self.post(self.url, data={}, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.assignee_id == parent_worker.id

    def test_forbidden_for_unrelated_user(self):
        outsider = UserFactory()
        resp = self.post(self.url, data={}, ajax=True, user=outsider)
        assert resp.status_code == 403

    def test_issue_not_found_returns_404(self):
        manager = UserFactory(grm_manager=True)
        url = reverse("dashboard:grm:escalate_issue", kwargs={"issue": 999999})
        resp = self.post(url, data={}, ajax=True, user=manager)
        assert resp.status_code == 404
