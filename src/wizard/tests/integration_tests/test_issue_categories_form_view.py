from django.urls import reverse

from authentication.factories import UserFactory
from grm.constants import (
    CATEGORY_DELETE_ERROR_MESSAGE,
    CATEGORY_TOAST_ERROR_MESSAGE,
    COMPLETED_CHOICE,
    FEWER_ISSUES_CHOICE,
    IN_PROGRESS_CHOICE,
    LOW_CHOICE,
    NOT_PERMITTED_TEXT,
)
from grm.tests.base import ViewTestCase
from issues.factories import (
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueFactory,
    IssueSubTypeFactory,
)
from issues.models import IssueCategory, IssueSubType
from wizard.models import WizardSection


class IssueCategoriesFormViewTest(ViewTestCase):
    """Integration tests for the IssueCategoriesFormView (step 5)."""

    def setUp(self):
        super().setUp()
        self.url = reverse("wizard:setup_step_5")
        self.user = UserFactory(grm_manager=True)

        self.current_section = WizardSection.objects.get(id=5)
        WizardSection.objects.filter(id=5).update(status=IN_PROGRESS_CHOICE)
        self.next_section = WizardSection.objects.get(id=6)
        self.other_required_fields = {
            "form-0-assigned_department": IssueDepartmentAdministrativeLevelFactory().id,
            "form-0-assigned_appeal_department": IssueDepartmentAdministrativeLevelFactory().id,
            "form-0-assigned_escalation_department": IssueDepartmentAdministrativeLevelFactory().id,
            "form-0-confidentiality_level": LOW_CHOICE,
            "form-0-redirection_protocol": FEWER_ISSUES_CHOICE,
        }

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

    def test_get_ajax_request_renders(self):
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn("formset", response.context)
        self.assertEqual(response.context["step"], 5)
        self.assertEqual(response.context["formset_label"], "Categories")
        self.assertEqual(response.context["toast_title"], NOT_PERMITTED_TEXT)
        self.assertEqual(response.context["toast_message"], CATEGORY_TOAST_ERROR_MESSAGE)
        self.assertTrue(response.context["two_fields_by_row"])

    def test_post_creates_new_category_with_existing_subtype(self):
        """Submitting valid data with an existing IssueSubType should create a category."""
        subtype = IssueSubTypeFactory(name="Subtype A")
        self.assertEqual(IssueCategory.objects.count(), 0)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Category 1",
            "form-0-parent": subtype.id,
            **self.other_required_fields,
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_6"))
        self.assertEqual(IssueCategory.objects.count(), 1)
        category = IssueCategory.objects.first()
        self.assertEqual(category.name, "Category 1")
        self.assertEqual(category.parent, subtype)

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_post_creates_new_category_with_new_subtype_string(self):
        """Submitting valid data with a new string for parent should create IssueSubType automatically."""
        self.assertEqual(IssueCategory.objects.count(), 0)
        self.assertEqual(IssueSubType.objects.count(), 0)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Category X",
            "form-0-parent": "New Subtype",
            **self.other_required_fields,
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(IssueCategory.objects.count(), 1)
        category = IssueCategory.objects.first()
        self.assertIsNotNone(category.parent)
        self.assertEqual(category.parent.name, "New Subtype")
        self.assertEqual(IssueSubType.objects.count(), 1)

    def test_post_invalid_parent_empty_string(self):
        """Submitting with empty parent should raise 'required' validation error."""
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Category Y",
            "form-0-parent": "",
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)  # re-renders with error
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertFormError(response.context["formset"].forms[0], "parent", "This field is required.")
        self.assertEqual(IssueCategory.objects.count(), 0)

    def test_post_updates_existing_category(self):
        """Updating an existing category with a new name should succeed."""
        category = IssueCategoryFactory(name="Old Cat", parent=IssueSubTypeFactory(name="Subtype B"))
        updated_name = "Updated Cat"

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": category.id,
            "form-0-name": updated_name,
            "form-0-parent": category.parent.id,
            "form-0-assigned_department": category.assigned_department.id,
            "form-0-assigned_appeal_department": category.assigned_appeal_department.id,
            "form-0-assigned_escalation_department": category.assigned_escalation_department.id,
            "form-0-confidentiality_level": category.confidentiality_level,
            "form-0-redirection_protocol": category.redirection_protocol,
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.name, updated_name)

    def test_post_cannot_delete_restricted_category(self):
        """Deleting should fail if restricted_deletion=True (category is linked to an Issue)."""
        category = IssueCategoryFactory(name="Restricted Cat", parent=IssueSubTypeFactory())
        IssueFactory(category=category)  # creates dependency

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": category.id,
            "form-0-name": category.name,
            "form-0-parent": category.parent.id,
            "form-0-DELETE": "on",  # marked for deletion
            "form-1-name": "new",
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn(
            CATEGORY_DELETE_ERROR_MESSAGE % {"name": category.name},
            response.context["formset"].non_form_errors()[0],
        )
        self.assertTrue(IssueCategory.objects.filter(id=category.id).exists())

    def test_post_can_delete_non_restricted_category(self):
        """Deleting should succeed if restricted_deletion=False."""
        category = IssueCategoryFactory(name="Free Cat", parent=IssueSubTypeFactory())

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": category.id,
            "form-0-name": category.name,
            "form-0-parent": category.parent.id,
            "form-0-DELETE": "on",  # marked for deletion
            "form-1-name": "new",
            "form-1-abbreviation": category.abbreviation,
            "form-1-parent": category.parent.id,
            "form-1-assigned_department": category.assigned_department.id,
            "form-1-assigned_appeal_department": category.assigned_appeal_department.id,
            "form-1-assigned_escalation_department": category.assigned_escalation_department.id,
            "form-1-confidentiality_level": category.confidentiality_level,
            "form-1-redirection_protocol": category.redirection_protocol,
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_6"))
        self.assertFalse(IssueCategory.objects.filter(id=category.id).exists())

    def test_required_fields_validation(self):
        """Should return validation errors when required fields are missing or empty."""
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            # intentionally missing or empty required fields
            "form-0-name": "",
            "form-0-abbreviation": "",
            "form-0-parent": "",
            "form-0-assigned_department": "",
            "form-0-assigned_appeal_department": "",
            "form-0-assigned_escalation_department": "",
            "form-0-confidentiality_level": "",
            "form-0-redirection_protocol": "",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)

        formset = response.context["form"]
        form = formset.forms[0]
        errors = form.errors

        # Ensure all expected keys appear and contain the correct message
        fields = [
            "name",
            "parent",
            "assigned_department",
            "assigned_appeal_department",
            "assigned_escalation_department",
            "confidentiality_level",
            "redirection_protocol",
        ]
        for field in fields:
            self.assertEqual(errors[field][0], "This field is required.")

    def test_duplicate_name_validation_on_update(self):
        """Should raise a validation error if updating a category with a name that already exists."""
        # Create an existing subtype and two categories
        category_1 = IssueCategoryFactory()
        category_2 = IssueCategoryFactory()
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            # Category 1 (unchanged)
            "form-0-id": category_1.id,
            "form-0-name": category_1.name,
            "form-0-abbreviation": category_1.abbreviation,
            "form-0-parent": category_1.parent.id,
            "form-0-assigned_department": category_1.assigned_department.id,
            "form-0-assigned_appeal_department": category_1.assigned_appeal_department.id,
            "form-0-assigned_escalation_department": category_1.assigned_escalation_department.id,
            "form-0-confidentiality_level": category_1.confidentiality_level,
            "form-0-redirection_protocol": category_1.redirection_protocol,
            # Category 2 (attempt to rename with duplicate name)
            "form-1-id": category_2.id,
            "form-1-name": category_1.name,  # duplicate
            "form-1-abbreviation": category_2.abbreviation,
            "form-1-parent": category_2.parent.id,
            "form-1-assigned_department": category_2.assigned_department.id,
            "form-1-assigned_appeal_department": category_2.assigned_appeal_department.id,
            "form-1-assigned_escalation_department": category_2.assigned_escalation_department.id,
            "form-1-confidentiality_level": category_2.confidentiality_level,
            "form-1-redirection_protocol": category_2.redirection_protocol,
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)  # validation errors don't redirect

        formset = response.context["form"]
        form = formset.forms[1]
        errors = form.errors

        self.assertIn("name", errors, "Expected 'name' field to have a validation error")
        self.assertIn(
            "Issue Category with this Name already exists.",
            errors["name"],
            "Expected duplicate name validation message",
        )

        # Ensure category_2 has NOT been renamed in DB
        category_2_name = category_2.name
        category_2.refresh_from_db()
        self.assertEqual(category_2.name, category_2_name)

    def test_post_requires_minimum_one(self):
        """
        Should require at least one IssueCategory form to be valid.
        """
        IssueCategoryFactory()

        data = {
            "form-TOTAL_FORMS": "0",  # no forms submitted
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",  # formset requires at least one
            "form-MAX_NUM_FORMS": "100",
        }

        response = self.post(self.url, data, ajax=True)

        # The form should not be valid and should render the same template again
        self.assertEqual(response.status_code, 200)
        formset = response.context["formset"]

        # Should not create anything
        self.assertEqual(IssueCategory.objects.count(), 1)

        # Verify formset validation error due to min_num constraint
        non_form_errors = formset.non_form_errors()
        self.assertTrue(any("at least" in e.lower() or "minimum" in e.lower() for e in non_form_errors))

        # Wizard should stay in current section (not mark completed)
        self.current_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
