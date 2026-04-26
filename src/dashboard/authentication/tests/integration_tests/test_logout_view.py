import pytest
from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase


@pytest.mark.django_db
class LogoutViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.logout_url = reverse("dashboard:authentication:logout")
        self.login_url = reverse("dashboard:authentication:login")

    def test_logout_redirects_to_login_page(self):
        self.client.force_login(self.user)

        response = self.get(self.logout_url, authorized=False)

        assert response.status_code == 302
        assert response.url == self.login_url
