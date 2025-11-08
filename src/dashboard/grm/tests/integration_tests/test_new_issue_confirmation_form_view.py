from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import IssueFactory


class NewIssueConfirmationFormViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.issue = IssueFactory(confirmed=True, administrative_region=self.root_region)
        self.url = reverse("dashboard:grm:new_issue_step_6", kwargs={"issue": self.issue.id})

    def test_get_allowed_for_manager(self):
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200
