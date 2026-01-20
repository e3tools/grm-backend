from django.urls import reverse

from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory


class GetAncestorAdministrativeLevelsViewTest(DashboardTestCase):
    """
    Integration tests for GetAncestorAdministrativeLevelsView.

    This suite verifies that:
    - For a given region, the view returns its full ancestor chain
      excluding the root region.
    - For the root region itself, the view returns an empty list.
    - Unauthenticated requests (without login) are rejected
      according to the mixin behavior (404 in this case).
    """

    def setUp(self):
        super().setUp()
        # Build a hierarchy: root_region -> province -> state -> city -> district
        self.province = AdministrativeRegionFactory(parent=self.root_region)
        self.state = AdministrativeRegionFactory(parent=self.province)
        self.city = AdministrativeRegionFactory(parent=self.state)
        self.district = AdministrativeRegionFactory(parent=self.city)
        self.url = reverse("dashboard:grm:get_ancestor_administrative_levels")

    def test_get_returns_all_ancestors(self):
        """
        For a non-root region (city), the response should include
        its ancestors up to but not including the root region.
        """
        resp = self.get(f"{self.url}?region_id={self.city.id}", ajax=True)
        assert resp.status_code == 200
        data = resp.json()
        assert {item for item in data} == {self.city.id, self.state.id, self.province.id}

    def test_get_returns_empty_for_root_region(self):
        """
        For the root region, the response should be an empty list
        because it has no ancestors above it.
        """
        resp = self.get(f"{self.url}?region_id={self.root_region.id}", ajax=True)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_forbidden_for_unauthenticated(self):
        """
        Requests without authentication should be rejected.
        The mixin used returns 404 for unauthenticated AJAX calls.
        """
        resp = self.get(f"{self.url}?region_id={self.state.id}", authorized=False, ajax=True)
        assert resp.status_code == 404
