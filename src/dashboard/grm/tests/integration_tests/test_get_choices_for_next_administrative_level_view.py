from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import DashboardTestCase
from issues.factories import AdministrativeRegionFactory


class GetChoicesForNextAdministrativeLevelViewTest(DashboardTestCase):
    """
    Integration tests for GetChoicesForNextAdministrativeLevelView.
    Ensures that given a parent region, the next-level children are returned in JSON.
    """

    def setUp(self):
        super().setUp()
        # root_region is already created in DashboardTestCase
        self.child1 = AdministrativeRegionFactory(parent=self.root_region, name="Child A")
        self.child2 = AdministrativeRegionFactory(parent=self.root_region, name="Child B")
        self.grandchild = AdministrativeRegionFactory(parent=self.child1, name="Grandchild A1")
        self.url = reverse("dashboard:grm:get_choices_for_next_administrative_level")

    def test_get_returns_children_for_parent(self):
        manager = UserFactory(grm_manager=True)
        resp = self.get(f"{self.url}?parent_id={self.root_region.id}", ajax=True, user=manager)
        assert resp.status_code == 200

        data = resp.json()
        # Expected both child1 and child2, but not grandchild
        ids = [item["id"] for item in data]
        assert set(ids) == {self.child1.id, self.child2.id}

    def test_get_returns_empty_list_if_no_children(self):
        manager = UserFactory(grm_manager=True)
        resp = self.get(f"{self.url}?parent_id={self.grandchild.id}", ajax=True, user=manager)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_forbidden_for_unauthenticated(self):
        resp = self.get(f"{self.url}?parent_id={self.root_region.id}", authorized=False, ajax=True)
        # should return 404 depending on mixin
        assert resp.status_code == 404
