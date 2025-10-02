from django.urls import reverse

from authentication.factories import UserFactory
from grm.constants import (
    ADMINISTRATIVE_LEVEL_DELETE_ERROR_MESSAGE,
    ADMINISTRATIVE_LEVEL_TOAST_ERROR_MESSAGE,
    COMPLETED_CHOICE,
    IN_PROGRESS_CHOICE,
    NOT_PERMITTED_TEXT,
    NOT_STARTED_CHOICE,
)
from grm.tests.base import ViewTestCase
from issues.factories import (
    AdministrativeLevelFactory,
    AdministrativeRegionFactory,
    IssueFactory,
)
from issues.models import AdministrativeLevel
from wizard.models import WizardSection


class AdministrativeLevelsFormViewTest(ViewTestCase):
    """Integration tests for the AdministrativeLevelsFormView."""

    def setUp(self):
        super().setUp()
        self.url = reverse("wizard:setup_step_2")
        self.user = UserFactory(grm_manager=True)

        self.current_section = WizardSection.objects.get(id=2)
        WizardSection.objects.filter(id=2).update(status=IN_PROGRESS_CHOICE)
        self.next_section = WizardSection.objects.get(id=3)

    def test_redirect_if_not_logged_in(self):
        """Test to make the view return 404 to anonymous users."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_non_ajax_request_returns_404(self):
        """Test that non-AJAX requests return 404 due to AJAXRequestMixin."""
        response = self.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_manager_user_cannot_access(self):
        """Test that logged-in non grm manager users cannot access the view."""

        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_get_ajax_request_renders(self):
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn("formset", response.context)
        self.assertEqual(response.context["step"], 2)
        self.assertEqual(response.context["total_steps"], WizardSection.objects.count())
        self.assertEqual(response.context["formset_label"], "Administrative Level Names")
        self.assertEqual(response.context["toast_title"], NOT_PERMITTED_TEXT)
        self.assertEqual(response.context["toast_message"], ADMINISTRATIVE_LEVEL_TOAST_ERROR_MESSAGE)

    def test_post_creates_new_administrative_level(self):
        """Submitting valid data should create a new AdministrativeLevel."""
        self.assertEqual(AdministrativeLevel.objects.count(), 0)

        level_name = "Level 1"
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": level_name,
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_3"))

        self.assertEqual(AdministrativeLevel.objects.count(), 1)
        level = AdministrativeLevel.objects.first()
        self.assertEqual(level.name, level_name)

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_post_updates_existing_administrative_level(self):
        level = AdministrativeLevelFactory(name="Old Level")

        level_name = "Updated Level"
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": level.id,
            "form-0-name": level_name,
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        level.refresh_from_db()
        self.assertEqual(level.name, level_name)

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_invalid_form_does_not_update_administrative_levels(self):
        """Test that invalid form does not administrative levels or sections."""
        level = AdministrativeLevelFactory(name="level1")
        level2 = AdministrativeLevelFactory(name="level2")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": level.id,
            "form-0-name": " ",
            "form-1-id": level2.id,
            "form-1-name": "New name",
        }
        response = self.post(self.url, data, ajax=True)

        # Should re-render the form with errors (200, not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")

        # No levels updated
        self.assertTrue(AdministrativeLevel.objects.filter(id=level.id, name=level.name).exists())
        self.assertTrue(AdministrativeLevel.objects.filter(id=level2.id, name=level2.name).exists())

        # Sections should remain unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_duplicate_name_validation_on_create(self):
        """Test create with duplicate name."""
        level = AdministrativeLevelFactory()

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": level.id,
            "form-0-name": level.name,
            "form-1-name": level.name,
        }
        response = self.post(self.url, data, ajax=True)

        # Should re-render the form with errors (200, not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")

        # No levels created
        self.assertEqual(AdministrativeLevel.objects.count(), 1)

        # Sections should remain unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_duplicate_name_validation_on_update(self):
        """Test update with duplicate name."""
        level = AdministrativeLevelFactory(name="level1")
        level2 = AdministrativeLevelFactory(name="level2")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": level.id,
            "form-0-name": level.name,
            "form-1-id": level2.id,
            "form-1-name": level.name,
        }
        response = self.post(self.url, data, ajax=True)

        # Should re-render the form with errors (200, not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")

        # No levels updated
        self.assertTrue(AdministrativeLevel.objects.filter(id=level.id, name=level.name).exists())
        self.assertTrue(AdministrativeLevel.objects.filter(id=level2.id, name=level2.name).exists())

        # Sections should remain unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_post_cannot_delete_restricted_level(self):
        """Deletion should fail if restricted_deletion = True."""
        level = AdministrativeLevelFactory(name="Restricted Level")
        region = AdministrativeRegionFactory(administrative_level=level)
        IssueFactory(administrative_region=region)  # generates restricted_deletion=True

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": level.id,
            "form-0-name": level.name,
            "form-0-DELETE": "on",  # marked for deletion
        }
        response = self.post(self.url, data, ajax=True)

        # No redirect, the form is re-rendered with error
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn(
            ADMINISTRATIVE_LEVEL_DELETE_ERROR_MESSAGE % {"name": level.name},
            response.context["formset"].non_form_errors()[0],
        )
        self.assertTrue(AdministrativeLevel.objects.filter(id=level.id, name=level.name).exists())

        # Sections should remain unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_post_can_delete_non_restricted_level(self):
        """Deletion should succeed if restricted_deletion = False."""
        level = AdministrativeLevelFactory(name="Free Level")

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": level.id,
            "form-0-name": level.name,
            "form-0-DELETE": "on",  # marked for deletion
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_3"))
        self.assertEqual(AdministrativeLevel.objects.count(), 0)

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)
