from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import IssueFactory


class NewIssueDetailsFormViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.other_user = UserFactory()
        self.issue = IssueFactory(reporter=self.manager, confirmed=False, administrative_region=self.root_region)
        self.url = reverse("dashboard:grm:new_issue_step_3", kwargs={"issue": self.issue.id})

    def test_get_allowed_for_manager_reporter(self):
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200

    def test_get_403_if_user_without_role(self):
        resp = self.get(self.url, user=self.other_user)
        assert resp.status_code == 403

    def test_get_404_if_authorized_but_not_reporter(self):
        from authentication.models import GovernmentWorker
        from issues.factories import IssueDepartmentFactory

        dept = IssueDepartmentFactory()
        worker_user = UserFactory()
        GovernmentWorker.objects.create(
            user=worker_user,
            department=dept,
            administrative_region=self.root_region,
        )

        resp = self.get(self.url, user=worker_user)
        assert resp.status_code == 404
