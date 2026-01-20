from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory, IssueFactory


class DeEscalateIssueViewTest(DashboardTestCase):
    """Integration tests for DeEscalateIssueView."""

    def setUp(self):
        super().setUp()
        # Build a small tree: root -> region_a -> region_b
        self.region_a = AdministrativeRegionFactory(parent=self.root_region)
        self.region_b = AdministrativeRegionFactory(parent=self.region_a)

        # Issue is at region_a; its current assignee will be a worker at region_a
        self.issue = IssueFactory(confirmed=True, administrative_region=self.region_a)
        # Make the current assignee a GovernmentWorker in region_a
        GovernmentWorkerFactory(
            user=self.issue.assignee,
            administrative_region=self.region_a,
            department=self.issue.category.assigned_department.department,
        )

        self.url = reverse("dashboard:grm:de_escalate_issue", kwargs={"issue": self.issue.id})

    def test_post_success_by_grm_manager_deescalates_to_child_worker(self):
        # Create a worker at child region_b in the same department
        child_worker = GovernmentWorkerFactory(
            administrative_region=self.region_b,
            department=self.issue.category.assigned_department.department,
        ).user

        manager = UserFactory(grm_manager=True)
        resp = self.post(self.url, data={}, ajax=True, user=manager)
        assert resp.status_code == 200
        data = resp.json()
        assert "msg" in data
        assert data.get("assignee", {}).get("id") == child_worker.id
        assert data.get("access_denied") is False

        self.issue.refresh_from_db()
        assert self.issue.assignee_id == child_worker.id

    def test_post_no_candidate_returns_error_message(self):
        # No GovernmentWorker in descendants; ensure region_a has no children workers
        manager = UserFactory(grm_manager=True)
        resp = self.post(self.url, data={}, ajax=True, user=manager)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("assignee") is None
        assert "msg" in data

        # Assignee unchanged
        self.issue.refresh_from_db()
        assert self.issue.assignee_id == self.issue.assignee.id

    def test_post_by_assignee_piu_staff_allowed(self):
        # Create a worker at child region_b to de-escalate to
        child_worker = GovernmentWorkerFactory(
            administrative_region=self.region_b,
            department=self.issue.category.assigned_department.department,
        ).user

        resp = self.post(self.url, data={}, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 200
        self.issue.refresh_from_db()
        assert self.issue.assignee_id == child_worker.id

    def test_forbidden_for_unrelated_user(self):
        outsider = UserFactory()
        resp = self.post(self.url, data={}, ajax=True, user=outsider)
        assert resp.status_code == 403

    def test_issue_not_found_returns_404(self):
        manager = UserFactory(grm_manager=True)
        url = reverse("dashboard:grm:de_escalate_issue", kwargs={"issue": 999999})
        resp = self.post(url, data={}, ajax=True, user=manager)
        assert resp.status_code == 404
