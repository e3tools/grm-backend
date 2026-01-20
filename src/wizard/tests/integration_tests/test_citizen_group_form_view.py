from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import ViewTestCase
from issues.factories import CitizenGroupFactory
from issues.models import CitizenGroup
from wizard.constants import (
    CITIZEN_GROUP_CHOICE,
    CITIZEN_GROUPS_CHOICE,
    COMPLETED_CHOICE,
    IN_PROGRESS_CHOICE,
    ITEM_TOAST_ERROR_MESSAGE,
    NOT_PERMITTED_TEXT,
)
from wizard.models import WizardSection
from wizard.registry import get_next_step, get_step_by_name


class CitizenGroupsFormViewTest(ViewTestCase):
    """Integration tests for the CitizenGroupsFormView."""

    def setUp(self):
        super().setUp()
        self.step = get_step_by_name(CITIZEN_GROUPS_CHOICE)['step']
        self.url = reverse(f"wizard:setup_step_{self.step}")
        self.user = UserFactory(grm_owner=True)

        # Wizard sections
        self.current_section = WizardSection.objects.get(step=self.step)
        self.current_section.status = IN_PROGRESS_CHOICE
        self.current_section.save()

        next_step_config = get_next_step(CITIZEN_GROUPS_CHOICE)
        self.next_section = WizardSection.objects.get(step=next_step_config['step'])

    def test_redirect_if_not_logged_in(self):
        """Anonymous users should get a 404."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_non_ajax_request_returns_404(self):
        """Non-AJAX requests should return 404."""
        response = self.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_owner_user_cannot_access(self):
        """Non-GRM manager users should not access the view."""
        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_get_ajax_request_renders(self):
        """View should render correctly with expected context."""
        response = self.get(self.url, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")

        context = response.context
        self.assertIn("formset", context)
        self.assertEqual(context["step"], self.step)
        self.assertEqual(context["formset_label"], "Citizen Groups")
        self.assertEqual(context["toast_title"], NOT_PERMITTED_TEXT)
        self.assertEqual(context["toast_message"], ITEM_TOAST_ERROR_MESSAGE)
        self.assertTrue(context["skip"])

    def test_post_creates_new_group(self):
        """Submitting valid data should create a new CitizenGroup."""
        self.assertEqual(CitizenGroup.objects.count(), 0)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Name",
            "form-0-type": CITIZEN_GROUP_CHOICE,
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))
        self.assertEqual(CitizenGroup.objects.count(), 1)

        group = CitizenGroup.objects.first()
        self.assertEqual(group.name, "Name")
        self.assertEqual(group.type, CITIZEN_GROUP_CHOICE)

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_post_updates_existing_group(self):
        """Updating an existing CitizenGroup should succeed."""
        group = CitizenGroupFactory(name="Old Name")

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": group.id,
            "form-0-name": "Updated Name",
            "form-0-type": CITIZEN_GROUP_CHOICE,
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))

        group.refresh_from_db()
        self.assertEqual(group.name, "Updated Name")

    def test_post_can_delete_group(self):
        """Deleting an existing CitizenGroup should remove it."""
        group = CitizenGroupFactory()
        self.assertEqual(CitizenGroup.objects.count(), 1)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": group.id,
            "form-0-name": group.name,
            "form-0-type": group.type,
            "form-0-DELETE": "on",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))
        self.assertEqual(CitizenGroup.objects.count(), 0)

    def test_required_name_validation(self):
        """Should return validation error when required name is empty."""
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "",
            "form-0-type": CITIZEN_GROUP_CHOICE,
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")

        formset = response.context["form"]
        form = formset.forms[0]
        self.assertIn("name", form.errors)
        self.assertEqual(form.errors["name"][0], "This field is required.")

    def test_required_type_validation(self):
        """Should return validation error when required type is empty."""
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Name",
            "form-0-type": "",
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")

        formset = response.context["form"]
        form = formset.forms[0]
        self.assertIn("type", form.errors)
        self.assertEqual(form.errors["type"][0], "This field is required.")

    def test_duplicate_name_validation_on_update(self):
        """Should raise validation error when updating with a duplicate name."""
        group1 = CitizenGroupFactory()
        group2 = CitizenGroupFactory()

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            # Group 1 unchanged
            "form-0-id": group1.id,
            "form-0-name": group1.name,
            "form-0-type": CITIZEN_GROUP_CHOICE,
            # Group 2 duplicated
            "form-1-id": group2.id,
            "form-1-name": group1.name,
            "form-1-type": CITIZEN_GROUP_CHOICE,
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"].forms[1]
        self.assertIn("name", form.errors)
        self.assertIn("Citizen Group with this Name already exists.", form.errors["name"][0])

        group2_name = group2.name
        group2.refresh_from_db()
        self.assertEqual(group2.name, group2_name)

    def test_duplicate_name_validation_on_create(self):
        """Should raise validation error when creating with a duplicate name."""

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Duplicate Name",
            "form-0-type": CITIZEN_GROUP_CHOICE,
            "form-1-name": "Duplicate Name",
            "form-1-type": CITIZEN_GROUP_CHOICE,
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CitizenGroup.objects.count(), 0)

        self.assertEqual(response.context["form"].errors[1]["__all__"][0], "Please correct the duplicate values below.")

    def test_skip_to_the_next_step_if_formset_is_empty(self):
        """Submitting an empty form should not create a CitizenGroup
        and skip to the next step marking the current one as completed."""

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "",
            "form-0-type": "",
            "form-1-name": "",
            "form-1-type": "",
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))
        self.assertEqual(CitizenGroup.objects.count(), 0)

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)
