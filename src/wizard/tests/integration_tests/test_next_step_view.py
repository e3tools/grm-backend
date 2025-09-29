from django.urls import reverse

from grm.constants import COMPLETED_CHOICE, IN_PROGRESS_CHOICE, NOT_STARTED_CHOICE
from grm.tests.base import ViewTestCase
from wizard.factories import WizardSectionFactory
from wizard.models import WizardSection


class NextStepViewTest(ViewTestCase):
    """Integration tests for the CustomizationWizardView."""

    def setUp(self):
        # Remove all WizardSections created by the migration
        WizardSection.objects.all().delete()

        # Create three wizard sections
        self.sections = WizardSectionFactory.create_batch(3, status=NOT_STARTED_CHOICE)
        self.url = lambda step: reverse("wizard:next_step", kwargs={"step": step})

    def test_redirect_if_not_logged_in(self):
        """Test to make the view return 404 to anonymous users."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_post_with_incomplete_section_does_not_increment_step(self):
        """
        If the current section is not completed,
        the view should return the same step and not update any section.
        """
        current_step = 1
        response = self.post(self.url(current_step), {}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"step": current_step})

        # No section should have changed to IN_PROGRESS
        self.assertFalse(WizardSection.objects.filter(status=IN_PROGRESS_CHOICE).exists())

    def test_post_with_completed_section_moves_to_next_step(self):
        """
        If the current section is completed,
        the next section should be set to IN_PROGRESS and step incremented.
        """
        # Mark section 1 as completed
        self.sections[0].status = COMPLETED_CHOICE
        self.sections[0].save()

        current_step = 1
        response = self.post(self.url(current_step), {}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"step": current_step + 1})

        # The second section should now be IN_PROGRESS
        self.sections[1].refresh_from_db()
        self.assertEqual(self.sections[1].status, IN_PROGRESS_CHOICE)

    def test_post_with_last_completed_section_does_not_break(self):
        """
        If the last section is completed, there is no next step to update,
        so the view should safely return the same step.
        """
        # Mark the last section as completed
        last_step = len(self.sections)
        self.sections[-1].status = COMPLETED_CHOICE
        self.sections[-1].save()

        response = self.post(self.url(last_step), {}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"step": last_step})

        # No section should be changed to IN_PROGRESS
        self.assertFalse(WizardSection.objects.filter(status=IN_PROGRESS_CHOICE).exists())
