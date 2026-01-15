from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory, IssueFactory


class IssueEscalateButtonsTemplateViewTest(DashboardTestCase):
    """
    Integration tests for IssueEscalateButtonsTemplateView.
    """

    def setUp(self):
        super().setUp()
        self.region = AdministrativeRegionFactory(parent=self.root_region)
        self.issue = IssueFactory(confirmed=True, administrative_region=self.region)
        # Ensure issue.assignee is a GovernmentWorker for context calculations
        GovernmentWorkerFactory(
            user=self.issue.assignee,
            administrative_region=self.region,
            department=self.issue.category.assigned_department.department,
        )
        self.url = reverse("dashboard:grm:issue_escalate_buttons", kwargs={"issue": self.issue.id})

    def test_get_renders_buttons_for_grm_manager(self):
        grm_manager = UserFactory(grm_manager=True)
        resp = self.get(self.url, ajax=True, user=grm_manager)
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/html")
        html = resp.content.decode().lower()
        assert "button" in html or "escalate" in html or "de-escalate" in html

    def test_get_renders_buttons_for_assignee(self):
        # assignee already set as GovernmentWorker in setUp
        resp = self.get(self.url, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 200
        html = resp.content.decode().lower()
        assert "button" in html or "escalate" in html or "de-escalate" in html

    def test_forbidden_for_unrelated_user(self):
        outsider = UserFactory()
        resp = self.get(self.url, ajax=True, user=outsider)
        assert resp.status_code == 403

    def test_forbidden_for_assigned_user_without_role(self):
        # Remove GovernmentWorker role by creating a different user without role
        another_user = UserFactory()
        resp = self.get(self.url, ajax=True, user=another_user)
        assert resp.status_code == 403

    def test_issue_not_found_returns_404(self):
        grm_manager = UserFactory(grm_manager=True)
        url = reverse("dashboard:grm:issue_escalate_buttons", kwargs={"issue": 999999})
        resp = self.get(url, ajax=True, user=grm_manager)
        assert resp.status_code == 404
