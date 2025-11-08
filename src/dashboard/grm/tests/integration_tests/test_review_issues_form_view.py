from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase


class ReviewIssuesFormViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("dashboard:grm:review_issues")
        self.user = UserFactory()
        self.manager = UserFactory(grm_manager=True)

    def test_get_accessible_when_logged_in(self):
        resp = self.get(self.url, user=self.user)
        assert resp.status_code == 200

    def test_get_accessible_for_manager(self):
        resp = self.get(self.url, user=self.manager)
        assert resp.status_code == 200
