from django.urls import reverse

from dashboard.diagnostics.views import HomeTemplateView
from grm.tests import DashboardTestCase


class TestHomeTemplateView(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse('dashboard:diagnostics:home')

    def test_auth_permission(self):
        response = self.get(self.url, authorized=False)

        assert response.status_code == 302

    def test_context_data(self):
        with self.assertNumQueries(18):
            response = self.get(self.url)
        context_data = response.context_data

        assert response.status_code == 200
        assert context_data['title'] == HomeTemplateView.title == 'Diagnostics'
        assert context_data['active_level1'] == HomeTemplateView.active_level1 == 'diagnostics'
        assert context_data['active_level2'] == HomeTemplateView.active_level2 is None
        assert context_data['breadcrumb'] == HomeTemplateView.breadcrumb is None
        assert isinstance(context_data['view'], HomeTemplateView)
