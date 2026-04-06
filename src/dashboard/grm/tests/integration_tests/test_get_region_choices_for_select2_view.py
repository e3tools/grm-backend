from django.urls import reverse

from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory


class GetRegionChoicesForSelect2ViewTest(DashboardTestCase):
    """
    Integration tests for GetRegionChoicesForSelect2View.

    Verifies that:
    - Authenticated AJAX requests return JSON with regions filtered by id or query.
    - Unauthenticated requests are rejected (404).
    """

    def setUp(self):
        super().setUp()
        self.url = reverse("dashboard:grm:get_region_choices_for_select2")
        # Create some regions with levels
        self.region_a = AdministrativeRegionFactory(name="Alpha", parent=self.root_region)
        self.region_b = AdministrativeRegionFactory(name="Beta", parent=self.root_region)
        self.region_c = AdministrativeRegionFactory(name="Gamma", parent=self.root_region)

    def test_get_with_selected_id_returns_single_region(self):
        resp = self.get(f"{self.url}?id={self.region_b.id}", ajax=True)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == self.region_b.id
        assert data[0]["text"] == str(self.region_b)

    def test_get_with_query_returns_matching_regions(self):
        resp = self.get(f"{self.url}?q=al", ajax=True)
        assert resp.status_code == 200
        data = resp.json()
        # Only region_a should match "al"
        ids = [item["id"] for item in data]
        assert self.region_a.id in ids
        assert self.region_b.id not in ids
        assert self.region_c.id not in ids

    def test_get_without_filters_returns_all_regions(self):
        resp = self.get(self.url, ajax=True)
        assert resp.status_code == 200
        data = resp.json()
        # Should include all created regions (limited to 10)
        ids = {item["id"] for item in data}
        assert {self.region_a.id, self.region_b.id, self.region_c.id}.issubset(ids)

    def test_get_forbidden_for_unauthenticated(self):
        resp = self.get(self.url, authorized=False, ajax=True)
        assert resp.status_code == 404
