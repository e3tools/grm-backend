from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import ViewTestCase
from wizard.constants import (
    ADMINISTRATIVE_LEVELS_CHOICE,
    ADMINISTRATIVE_REGIONS_CHOICE,
    COMPLETED_CHOICE,
    IN_PROGRESS_CHOICE,
    MAP_WIZARD_SECTION,
    NOT_STARTED_CHOICE,
    PROJECT_CHOICE,
)
from wizard.factories import WizardSectionFactory
from wizard.models import WizardSection


class WizardSectionListViewTest(ViewTestCase):
    """Integration tests for the WizardSectionListView."""

    def setUp(self):
        """Set up test data and URL for each test."""
        self.url = reverse("wizard:wizard_section_list")
        self.user = UserFactory(grm_manager=True)

        # remove all WizardSections created by the migration
        WizardSection.objects.all().delete()

        # Create test wizard sections
        self.section1 = WizardSectionFactory(id=2, step=1, status=COMPLETED_CHOICE, name=PROJECT_CHOICE)
        self.section2 = WizardSectionFactory(id=1, step=2, status=IN_PROGRESS_CHOICE, name=ADMINISTRATIVE_LEVELS_CHOICE)
        self.section3 = WizardSectionFactory(
            id=3, step=3, status=NOT_STARTED_CHOICE, name=ADMINISTRATIVE_REGIONS_CHOICE
        )

    def test_redirect_if_not_logged_in(self):
        """Test to make the view return 404 to anonymous users."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_manager_user_cannot_access(self):
        """Test that logged-in non grm manager users cannot access the view."""

        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_ajax_request_returns_success(self):
        """Test that AJAX requests return successful response."""
        response = self.get(self.url, data={"step": 1}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, MAP_WIZARD_SECTION.get(self.section1.name))
        self.assertContains(response, MAP_WIZARD_SECTION.get(self.section2.name))
        self.assertContains(response, MAP_WIZARD_SECTION.get(self.section3.name))

    def test_non_ajax_request_returns_404(self):
        """Test that non-AJAX requests return 404 due to AJAXRequestMixin."""
        response = self.client.get(self.url, {"step": 1})

        self.assertEqual(response.status_code, 404)

    def test_context_contains_wizard_sections_and_step(self):
        """Test that the context contains wizard sections and step value."""
        response = self.get(self.url, data={"step": 2}, ajax=True)

        self.assertIn("wizard_sections", response.context)
        self.assertEqual(response.context["step"], 2)

        wizard_sections = response.context["wizard_sections"]

        # Check all sections are present
        section_names = [section.name for section in wizard_sections]
        self.assertIn(self.section1.name, section_names)
        self.assertIn(self.section2.name, section_names)
        self.assertIn(self.section3.name, section_names)

    def test_wizard_sections_ordering(self):
        """Test that wizard sections are returned in correct order (by id)."""
        response = self.get(self.url, data={"step": 1}, ajax=True)

        wizard_sections = list(response.context["wizard_sections"])

        # Should be ordered by step (as defined in model Meta)
        self.assertEqual(wizard_sections[0].id, self.section1.id)
        self.assertEqual(wizard_sections[1].id, self.section2.id)
        self.assertEqual(wizard_sections[2].id, self.section3.id)

    def test_template_used(self):
        """Test that the correct template is used."""
        response = self.get(self.url, data={"step": 1}, ajax=True)

        self.assertTemplateUsed(response, "wizard/wizard_sections.html")

    def test_empty_wizard_sections(self):
        """Test view behavior when no wizard sections exist."""
        WizardSection.objects.all().delete()

        response = self.get(self.url, data={"step": 1}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("wizard_sections", response.context)
        self.assertEqual(len(response.context["wizard_sections"]), 0)

    def test_section_with_different_statuses(self):
        """Test that sections with different statuses are all included."""
        response = self.get(self.url, data={"step": 1}, ajax=True)

        wizard_sections = response.context["wizard_sections"]
        statuses = [section.status for section in wizard_sections]

        self.assertIn(COMPLETED_CHOICE, statuses)
        self.assertIn(IN_PROGRESS_CHOICE, statuses)
        self.assertIn(NOT_STARTED_CHOICE, statuses)

    def test_section_fields_in_context(self):
        """Test that all wizard section fields are accessible in context."""
        response = self.get(self.url, data={"step": 1}, ajax=True)

        wizard_sections = response.context["wizard_sections"]
        first_section = wizard_sections.first()

        # Check that all model fields are accessible
        self.assertTrue(hasattr(first_section, "name"))
        self.assertTrue(hasattr(first_section, "status"))
        self.assertTrue(hasattr(first_section, "updated_at"))

    def test_response_content_type(self):
        """Test that response has correct content type."""
        response = self.get(self.url, data={"step": 1}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

    def test_post_method_not_allowed(self):
        """Test that POST method returns 405 Method Not Allowed."""
        response = self.post(self.url, {"step": 1}, ajax=True)

        self.assertEqual(response.status_code, 405)

    def test_put_method_not_allowed(self):
        """Test that PUT method returns 405 Method Not Allowed."""
        response = self.put(self.url, {"step": 1}, ajax=True)

        self.assertEqual(response.status_code, 405)

    def test_delete_method_not_allowed(self):
        """Test that DELETE method returns 405 Method Not Allowed."""
        response = self.delete(self.url, {"step": 1}, ajax=True)

        self.assertEqual(response.status_code, 405)
