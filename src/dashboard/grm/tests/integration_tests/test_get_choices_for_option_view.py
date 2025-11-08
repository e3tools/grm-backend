from django.urls import reverse

from grm.tests.base import DashboardTestCase
from issues.factories import ComponentFactory, SubComponentFactory


class GetChoicesForOptionViewTest(DashboardTestCase):
    """
    Integration tests for GetChoicesForOptionView.

    This suite verifies that:
    - Authenticated AJAX requests return the rendered options template
      with the expected values from the database.
    - Unauthenticated requests are rejected (404).
    """

    def setUp(self):
        super().setUp()
        self.url = reverse("dashboard:grm:get_options_values")
        # Create a parent Component and some SubComponents
        self.component = ComponentFactory(description="Main component")
        self.sub1 = SubComponentFactory(name="Sub 1", description="desc", parent=self.component)
        self.sub2 = SubComponentFactory(name="Sub 2", description="desc", parent=self.component)

    def test_get_returns_rendered_options_for_subcomponents(self):
        """
        For a valid request, the view should render 'common/options.html'
        with the SubComponents belonging to the given Component.
        """
        resp = self.get(f"{self.url}?model_class=SubComponent&parent_id={self.component.id}", ajax=True)

        assert resp.status_code == 200
        content = resp.content.decode()
        # The rendered HTML should contain the names of the subcomponents
        assert "Sub 1" in content
        assert "Sub 2" in content

    def test_get_forbidden_for_unauthenticated(self):
        """
        Requests without authentication should be rejected.
        The mixin used returns 404 for unauthenticated AJAX calls.
        """
        resp = self.get(
            f"{self.url}?model_class=SubComponent&parent_id={self.component.id}", authorized=False, ajax=True
        )
        assert resp.status_code == 404
