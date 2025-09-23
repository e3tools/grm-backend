import pytest
from django.test import TestCase
from django.urls import reverse

from dashboard.models import Project
from grm.constants import COMPLETED_CHOICE, IN_PROGRESS_CHOICE, NOT_STARTED_CHOICE
from wizard.factories import WizardSectionFactory
from wizard.models import WizardSection


@pytest.mark.django_db
class ProjectUpdateViewTest(TestCase):
    """Integration tests for the ProjectUpdateView."""

    def setUp(self):
        self.url = reverse("wizard:setup_step_1")

        # Remove all WizardSections created by the migration
        WizardSection.objects.all().delete()

        # Create ordered wizard sections
        self.section1 = WizardSectionFactory()
        self.section2 = WizardSectionFactory()

    def test_non_ajax_request_returns_404(self):
        """Test that non-AJAX requests return 404 due to AJAXRequestMixin."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_ajax_request_renders_form(self):
        """Test that GET request renders the form correctly via AJAX."""
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/form.html")

    def test_get_context_contains_step_and_total_steps(self):
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.context["step"], 1)
        self.assertEqual(response.context["total_steps"], WizardSection.objects.count())

    def test_post_creates_new_project_and_updates_sections(self):
        """Test that POST request creates a new project and updates sections."""
        self.assertEqual(Project.objects.count(), 0)

        project_name = "Test Project"
        project_description = "This is a test project."
        data = {"name": project_name, "description": project_description}
        response = self.client.post(self.url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        # Should redirect to success_url
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_2"))

        # Project should be created
        self.assertEqual(Project.objects.count(), 1)
        project = Project.objects.first()
        self.assertEqual(project.name, project_name)
        self.assertEqual(project.description, project_description)

        # Wizard sections should be updated
        self.section1.refresh_from_db()
        self.section2.refresh_from_db()
        self.assertEqual(self.section1.status, COMPLETED_CHOICE)
        self.assertEqual(self.section2.status, IN_PROGRESS_CHOICE)

    def test_post_updates_existing_project(self):
        """Test that POST request updates existing project instead of creating new one."""
        project = Project.objects.create(name="Old Project", description="Old description")
        self.assertEqual(Project.objects.count(), 1)

        project_name = "Updated Project"
        project_description = "Updated description"
        data = {"name": project_name, "description": project_description}
        response = self.client.post(self.url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_2"))

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
        response = self.client.post(self.url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

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
        response = self.client.post(self.url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        # Should re-render the form with errors (200, not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/form.html")

        # No project created
        self.assertEqual(Project.objects.count(), 0)

        # Sections should remain unchanged
        self.section1.refresh_from_db()
        self.section2.refresh_from_db()
        self.assertEqual(self.section1.status, NOT_STARTED_CHOICE)
        self.assertEqual(self.section2.status, NOT_STARTED_CHOICE)
