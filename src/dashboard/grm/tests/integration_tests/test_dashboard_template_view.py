from django.urls import reverse

from authentication.factories import UserFactory
from authentication.models import GovernmentWorker
from grm.tests.base import DashboardTestCase
from issues.factories import IssueDepartmentFactory


class DashboardTemplateViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
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
        self.url = reverse("dashboard:grm:dashboard")

    def test_permissions(self):
        # GRM Manager can access
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200

        # Government Worker (Case Manager) can access
        resp = self.get(self.url, user=self.worker_user)
        assert resp.status_code == 200

        # Normal user is denied
        resp = self.get(self.url, user=self.normal_user)
        assert resp.status_code == 403
