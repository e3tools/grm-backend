import importlib
import sys

from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings
from django.urls import clear_url_caches, reverse

from dashboard.authentication.views import handler500


class RootUrlsTest(TestCase):
    def setUp(self):
        super().setUp()
        self.request_factory = RequestFactory()

    def test_dashboard_login_page_is_resolvable(self):
        response = self.client.get(reverse("dashboard:authentication:login"))

        assert response.status_code == 200

    def test_admin_login_page_is_exposed(self):
        response = self.client.get(reverse("admin:login"))

        assert response.status_code == 200

    @override_settings(DEBUG=True)
    def test_swagger_route_is_exposed_in_debug_mode(self):
        clear_url_caches()
        urlconf = settings.ROOT_URLCONF
        if urlconf in sys.modules:
            importlib.reload(sys.modules[urlconf])

        response = self.client.get("/swagger/")

        assert response.status_code == 200

    def test_not_found_handler_returns_404_template(self):
        response = self.client.get("/route-that-does-not-exist/")
        assert response.status_code == 404

    def test_server_error_handler_returns_500(self):
        request = self.request_factory.get("/")
        response = handler500(request)
        assert response.status_code == 500
