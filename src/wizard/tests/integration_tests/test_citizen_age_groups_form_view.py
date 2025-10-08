from django.urls import reverse

from authentication.factories import UserFactory
from grm.constants import (
    COMPLETED_CHOICE,
    GROUP_DELETE_ERROR_MESSAGE,
    GROUP_TOAST_ERROR_MESSAGE,
    IN_PROGRESS_CHOICE,
    NOT_PERMITTED_TEXT,
)
from grm.tests.base import ViewTestCase
from issues.factories import CitizenAgeGroupFactory, CitizenFactory
from issues.models import CitizenAgeGroup
from wizard.forms import DEFAULT_CITIZEN_AGE_GROUPS
from wizard.models import WizardSection


class CitizenAgeGroupsFormViewTest(ViewTestCase):
    """Integration tests for the CitizenAgeGroupsFormView (step 7)."""

    def setUp(self):
        super().setUp()
        self.url = reverse("wizard:setup_step_7")
        self.user = UserFactory(grm_manager=True)

        # Wizard state setup
        self.current_section = WizardSection.objects.get(id=7)
        WizardSection.objects.filter(id=7).update(status=IN_PROGRESS_CHOICE)
        self.next_section = WizardSection.objects.get(id=8)

    # ---- Access control ----

    def test_redirect_if_not_logged_in(self):
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_non_ajax_request_returns_404(self):
        response = self.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_manager_user_cannot_access(self):
        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 404)

    # ---- Rendering ----

    def test_get_ajax_request_renders(self):
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn("formset", response.context)
        self.assertEqual(response.context["step"], 7)
        self.assertEqual(response.context["total_steps"], WizardSection.objects.count())
        self.assertEqual(response.context["formset_label"], "Citizen Age Groups")
        self.assertEqual(response.context["toast_title"], NOT_PERMITTED_TEXT)
        self.assertEqual(response.context["toast_message"], GROUP_TOAST_ERROR_MESSAGE)

    # ---- Creation logic ----

    def test_post_creates_default_age_groups_when_none_exist(self):
        """Should create the default CitizenAgeGroups if none exist yet."""
        self.assertEqual(CitizenAgeGroup.objects.count(), 0)

        data = {
            "form-TOTAL_FORMS": str(len(DEFAULT_CITIZEN_AGE_GROUPS)),
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }

        # Add each default age group
        for i, name in enumerate(DEFAULT_CITIZEN_AGE_GROUPS):
            data[f"form-{i}-name"] = name

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_8"))
        self.assertEqual(CitizenAgeGroup.objects.count(), len(DEFAULT_CITIZEN_AGE_GROUPS))

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    # ---- Update ----

    def test_post_updates_existing_age_group(self):
        """Should update an existing CitizenAgeGroup."""
        group = CitizenAgeGroupFactory(name="Under 12 or younger")
        updated_name = "Under 10 or younger"

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": group.id,
            "form-0-name": updated_name,
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)

        group.refresh_from_db()
        self.assertEqual(group.name, updated_name)

    # ---- Deletion ----

    def test_post_cannot_delete_restricted_age_group(self):
        """Should prevent deletion if the CitizenAgeGroup is linked to existing Citizen(s)."""
        group = CitizenAgeGroupFactory(name="35–44 years")
        CitizenFactory(age_group=group)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": group.id,
            "form-0-name": group.name,
            "form-0-DELETE": "on",
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn(
            GROUP_DELETE_ERROR_MESSAGE % {"name": group.name},
            response.context["formset"].non_form_errors()[0],
        )
        self.assertTrue(CitizenAgeGroup.objects.filter(id=group.id).exists())

    def test_post_can_delete_non_restricted_age_group(self):
        """Should delete successfully if no linked Citizens exist."""
        group = CitizenAgeGroupFactory(name="45–54 years")

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": group.id,
            "form-0-name": group.name,
            "form-0-DELETE": "on",
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_8"))
        self.assertEqual(CitizenAgeGroup.objects.count(), 0)

    # ---- Validation ----

    def test_required_field_validation(self):
        """Should return validation errors if 'name' is empty."""
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"].forms[0]
        self.assertIn("name", form.errors)
        self.assertEqual(form.errors["name"][0], "This field is required.")

    def test_duplicate_name_validation_on_update(self):
        """Should raise validation error when updating with a duplicate name."""
        group1 = CitizenAgeGroupFactory(name="18–24 years")
        group2 = CitizenAgeGroupFactory(name="25–34 years")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            # Group 1 unchanged
            "form-0-id": group1.id,
            "form-0-name": group1.name,
            # Group 2 duplicated
            "form-1-id": group2.id,
            "form-1-name": group1.name,
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"].forms[1]
        self.assertIn("name", form.errors)
        self.assertIn("Citizen Age Group with this Name already exists.", form.errors["name"][0])

        group2.refresh_from_db()
        self.assertEqual(group2.name, "25–34 years")

    def test_duplicate_name_validation_on_create(self):
        """Should raise validation error when creating with a duplicate name."""

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Duplicate Name",
            "form-1-name": "Duplicate Name",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CitizenAgeGroup.objects.count(), 0)

        self.assertEqual(response.context["form"].errors[1]["__all__"][0], "Please correct the duplicate values below.")
