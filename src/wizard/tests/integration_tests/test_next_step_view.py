from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import ViewTestCase
from wizard.constants import COMPLETED_CHOICE, IN_PROGRESS_CHOICE, NOT_STARTED_CHOICE
from wizard.models import WizardSection


class NextStepViewTest(ViewTestCase):
    """Integration tests for the CustomizationWizardView."""

    def setUp(self):
        self.user = UserFactory(grm_owner=True)
        self.sections = WizardSection.objects.all()
        self.url = lambda step: reverse("wizard:next_step", kwargs={"step": step})

    def test_redirect_if_not_logged_in(self):
        """Test to make the view return 404 to anonymous users."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_owner_user_cannot_access(self):
        """Test that logged-in non grm manager users cannot access the view."""

        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
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

        # No section should have changed status
        self.assertTrue(WizardSection.objects.filter(id=self.sections[0].id, status=IN_PROGRESS_CHOICE).exists())
        self.assertEqual(WizardSection.objects.filter(status=NOT_STARTED_CHOICE).count(), len(self.sections) - 1)

    def test_post_with_completed_section_moves_to_next_step(self):
        """
        If the current section is completed,
        the next section should be set to IN_PROGRESS and step incremented.
        """
        # Mark section 1 as completed
        WizardSection.objects.filter(id=self.sections[0].id).update(status=COMPLETED_CHOICE)

        current_step = 1
        response = self.post(self.url(current_step), {}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"step": current_step + 1})

        # The second section should now be IN_PROGRESS
        self.sections[1].refresh_from_db()
        self.assertEqual(self.sections[1].status, IN_PROGRESS_CHOICE)

    def test_post_with_next_step_completed_the_status_does_not_change(self):
        """
        If the next step is completed, its status should not be changed to in_progress.
        """
        # Mark all sections as completed
        WizardSection.objects.update(status=COMPLETED_CHOICE)

        current_step = 1
        response = self.post(self.url(current_step), {}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"step": current_step + 1})

        # No section should be changed to IN_PROGRESS
        self.assertFalse(WizardSection.objects.filter(status=IN_PROGRESS_CHOICE).exists())
