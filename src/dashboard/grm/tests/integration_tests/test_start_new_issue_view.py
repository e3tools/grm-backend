from django.urls import reverse

from authentication.factories import UserFactory
from authentication.models import GovernmentWorker
from grm.tests.base import DashboardTestCase
from issues.factories import IssueDepartmentFactory, IssueStatusFactory
from issues.models import Issue


class StartNewIssueViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("dashboard:grm:start_new_issue")

        # Users
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()

        # Government worker linked to existing root_region from DashboardTestCase
        self.department = IssueDepartmentFactory()
        self.worker_user = UserFactory()
        GovernmentWorker.objects.create(
            user=self.worker_user,
            department=self.department,
            administrative_region=self.root_region,
        )

        # Ensure an initial IssueStatus exists (required by the view)
        IssueStatusFactory(initial_status=True)

    def test_permissions_and_redirect(self):
        # Normal user cannot start a new issue
        resp = self.post(self.url, {}, user=self.normal_user, follow=True)
        assert resp.status_code == 403

        # GRM Manager can start a new issue
        count_before = Issue.objects.count()
        resp = self.post(self.url, {}, user=self.manager, follow=False)
        assert resp.status_code == 302
        assert Issue.objects.count() == count_before + 1

        # Government Worker can start a new issue
        count_before = Issue.objects.count()
        resp = self.post(self.url, {}, user=self.worker_user, follow=False)
        assert resp.status_code == 302
        assert Issue.objects.count() == count_before + 1
