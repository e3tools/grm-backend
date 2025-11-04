from django.urls import reverse

from authentication.factories import UserFactory
from dashboard.models import Project
from grm.tests.base import ViewTestCase
from wizard.constants import (
    COMPLETED_CHOICE,
    IN_PROGRESS_CHOICE,
    NOT_STARTED_CHOICE,
    PROJECT_CHOICE,
)
from wizard.models import WizardSection
from wizard.registry import get_next_step, get_step_by_name


class ProjectUpdateViewTest(ViewTestCase):
    """Integration tests for the ProjectUpdateView."""

    def setUp(self):
        super().setUp()
        self.step = get_step_by_name(PROJECT_CHOICE)['step']
        self.url = reverse(f"wizard:setup_step_{self.step}")
        self.user = UserFactory(grm_owner=True)

        # Wizard sections
        self.current_section = WizardSection.objects.get(step=self.step)
        self.current_section.status = IN_PROGRESS_CHOICE
        self.current_section.save()

        next_step_config = get_next_step(PROJECT_CHOICE)
        self.next_section = WizardSection.objects.get(step=next_step_config['step'])

    def test_redirect_if_not_logged_in(self):
        """Test to make the view return 404 to anonymous users."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_owner_user_cannot_access(self):
        """Test that logged-in non grm manager users cannot access the view."""

        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_non_ajax_request_returns_404(self):
        """Test that non-AJAX requests return 404 due to AJAXRequestMixin."""
        response = self.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_ajax_request_renders_form(self):
        """Test that GET request renders the form correctly via AJAX."""
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/form.html")

    def test_get_context_contains_step(self):
        """Test that context includes step and total steps."""
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.context["step"], self.step)

    def test_post_creates_new_project_and_updates_sections(self):
        """Test that POST request creates a new project and updates sections."""
        self.assertEqual(Project.objects.count(), 0)

        project_name = "Test Project"
        project_description = "This is a test project."
        data = {"name": project_name, "description": project_description}
        response = self.post(self.url, data, ajax=True)

        # Should redirect to success_url
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))

        # Project should be created
        self.assertEqual(Project.objects.count(), 1)
        project = Project.objects.first()
        self.assertEqual(project.name, project_name)
        self.assertEqual(project.description, project_description)

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_post_updates_existing_project(self):
        """Test that POST request updates existing project instead of creating new one."""
        project = Project.objects.create(name="Old Project", description="Old description")
        self.assertEqual(Project.objects.count(), 1)

        project_name = "Updated Project"
        project_description = "Updated description"
        data = {"name": project_name, "description": project_description}
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))

        # Still only one project
        self.assertEqual(Project.objects.count(), 1)

        project.refresh_from_db()
        self.assertEqual(project.name, project_name)
        self.assertEqual(project.description, project_description)

    def test_post_updates_existing_project_with_empty_description(self):
        """Test that POST request updates existing project without description."""
        project = Project.objects.create(name="Old Project", description="Old description")
        self.assertEqual(Project.objects.count(), 1)

        project_name = "Updated Project"
        data = {"name": project_name, "description": ""}
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_2"))

        # Still only one project
        self.assertEqual(Project.objects.count(), 1)

        project.refresh_from_db()
        self.assertEqual(project.name, project_name)
        self.assertEqual(project.description, "")

    def test_invalid_form_does_not_update_sections(self):
        """Test that invalid form does not update project or sections."""
        data = {"name": "", "description": ""}  # Invalid because name is required
        response = self.post(self.url, data, ajax=True)

        # Should re-render the form with errors (200, not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/form.html")

        # No project created
        self.assertEqual(Project.objects.count(), 0)

        # Sections should remain unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_update_status_does_not_override_next_section(self):
        """Test that update_status does not override if next section already has different status."""
        # Mark section2 as already IN_PROGRESS
        self.next_section.status = IN_PROGRESS_CHOICE
        self.next_section.save()

        data = {"name": "Test Project", "description": "desc"}
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)

        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()

        # section1 should still become COMPLETED
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)

        # section2 should remain IN_PROGRESS (not overridden)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)
