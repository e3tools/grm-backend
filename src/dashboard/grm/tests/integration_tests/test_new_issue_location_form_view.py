from django.urls import reverse

from authentication.factories import UserFactory
from authentication.models import GovernmentWorker
from grm.tests.base import DashboardTestCase
from issues.factories import (
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
    IssueFactory,
)


class NewIssueLocationFormViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        # Reporter is a government worker to expose government_worker_id in context
        self.worker_user = UserFactory()
        dep = IssueDepartmentFactory(head=self.worker_user)
        dep_level = IssueDepartmentAdministrativeLevelFactory(department=dep)
        category = IssueCategoryFactory(assigned_department=dep_level)
        GovernmentWorker.objects.create(
            user=self.worker_user,
            department=dep,
            administrative_region=self.root_region,
        )
        self.other_user = UserFactory()
        self.issue = IssueFactory(
            reporter=self.worker_user, confirmed=False, category=category, administrative_region=self.root_region
        )
        self.url = reverse("dashboard:grm:new_issue_step_4", kwargs={"issue": self.issue.id})

    def test_get_allowed_and_context_has_worker_id(self):
        resp = self.get(self.url, user=self.worker_user)
        assert resp.status_code == 200
        ctx = self.get_context(resp)
        assert ctx.get("government_worker_id") is not None

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
