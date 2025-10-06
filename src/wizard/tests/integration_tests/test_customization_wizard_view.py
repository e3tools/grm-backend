from django.urls import reverse

from authentication.factories import UserFactory
from grm.constants import IN_PROGRESS_CHOICE
from grm.tests.base import ViewTestCase
from wizard.factories import WizardSectionFactory
from wizard.models import WizardSection


class CustomizationWizardViewTest(ViewTestCase):
    """Integration tests for the CustomizationWizardView."""

    def setUp(self):
        self.url = reverse("wizard:customization_wizard")
        self.user = UserFactory(grm_manager=True)

    def test_redirect_if_not_logged_in(self):
        """Test to make the view return 404 to anonymous users."""
        response = self.get(self.url, authorized=False)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_manager_user_cannot_access(self):
        """Test that logged-in non grm manager users cannot access the view."""

        self.user = UserFactory()
        response = self.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_user_can_access(self):
        """Test that logged-in users can access the view."""

        response = self.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/grm_customization.html")

    def test_context_current_step(self):
        """Test that current_step is correctly set."""

        # Remove all WizardSections created by the migration
        WizardSection.objects.all().delete()

        # Create 5 sections
        sections = WizardSectionFactory.create_batch(5)

        response = self.get(self.url)

        # No section is in progress or receiving a step parameter → current_step should equal total_steps
        self.assertEqual(response.context["current_step"], 5)

        # Mark one section as IN_PROGRESS and test again
        section_in_progress = sections[2]
        section_in_progress.status = IN_PROGRESS_CHOICE
        section_in_progress.save()

        response = self.get(self.url)
        # current_step should be the index of the in-progress section + 1
        self.assertEqual(response.context["current_step"], 3)

        # Pass the step parameter with the current step value
        response = self.get(self.url, {"step": 4})
        # current_step must be the same as the one passed in as parameter
        self.assertEqual(response.context["current_step"], '4')
