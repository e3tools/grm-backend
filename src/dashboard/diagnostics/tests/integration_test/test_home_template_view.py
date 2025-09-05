import pytest
from django.test import override_settings
from django.urls import reverse

from dashboard.diagnostics.views import HomeFormView
from grm.tests.base import DashboardTestCase


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class HomeFormViewTest(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("dashboard:diagnostics:home")

    def test_auth_permission(self):
        response = self.get(self.url, authorized=False)

        assert response.status_code == 302

    def test_context_data(self):
        response = self.get(self.url)
        context_data = response.context_data

        assert response.status_code == 200
        assert context_data["title"] == HomeFormView.title == "Diagnostics"
        assert context_data["active_level1"] == HomeFormView.active_level1 == "diagnostics"
        assert context_data["active_level2"] == HomeFormView.active_level2 is None
        assert context_data["breadcrumb"] == HomeFormView.breadcrumb is None
        assert isinstance(context_data["view"], HomeFormView)
