from django.urls import reverse

from authentication.factories import GovernmentWorkerFactory, UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory, IssueFactory


class IssueStatusButtonsTemplateViewTest(DashboardTestCase):
    """
    Integration tests for IssueStatusButtonsTemplateView.
    """

    def setUp(self):
        super().setUp()
        self.region = AdministrativeRegionFactory(parent=self.root_region)
        self.issue = IssueFactory(confirmed=True, administrative_region=self.region)
        self.url = reverse("dashboard:grm:issue_status_buttons", kwargs={"issue": self.issue.id})

    def test_get_renders_buttons_for_grm_manager(self):
        grm_manager = UserFactory(grm_manager=True)
        resp = self.get(self.url, ajax=True, user=grm_manager)
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/html")
        assert "button" in resp.content.decode().lower() or "status" in resp.content.decode().lower()

    def test_get_renders_buttons_for_assignee(self):
        GovernmentWorkerFactory(user=self.issue.assignee, administrative_region=self.root_region)
        resp = self.get(self.url, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "button" in html.lower() or "status" in html.lower()

    def test_forbidden_for_unrelated_user(self):
        outsider = UserFactory()
        resp = self.get(self.url, ajax=True, user=outsider)
        assert resp.status_code == 403

    def test_forbidden_for_assigned_user_without_role(self):
        resp = self.get(self.url, ajax=True, user=self.issue.assignee)
        assert resp.status_code == 403

    def test_issue_not_found_returns_404(self):
        grm_manager = UserFactory(grm_manager=True)
        url = reverse("dashboard:grm:issue_status_buttons", kwargs={"issue": 999999})
        resp = self.get(url, ajax=True, user=grm_manager)
        assert resp.status_code == 404
