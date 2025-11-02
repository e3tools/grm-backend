from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import ViewTestCase
from issues.factories import IssueCategoryFactory, IssueSubTypeFactory, IssueTypeFactory
from issues.models import IssueSubType, IssueType
from wizard.constants import (
    COMPLETED_CHOICE,
    IN_PROGRESS_CHOICE,
    ISSUE_TYPES_CHOICE,
    ITEM_DELETE_ERROR_MESSAGE,
    ITEM_TOAST_ERROR_MESSAGE,
    NOT_PERMITTED_TEXT,
    NOT_STARTED_CHOICE,
)
from wizard.forms import DEFAULT_ISSUE_TYPES
from wizard.models import WizardSection
from wizard.registry import get_next_step, get_step_by_name


class IssueTypesFormViewTest(ViewTestCase):
    """Integration tests for the IssueTypesFormView."""

    def setUp(self):
        super().setUp()
        self.step = get_step_by_name(ISSUE_TYPES_CHOICE)['step']
        self.url = reverse(f"wizard:setup_step_{self.step}")
        self.user = UserFactory(grm_manager=True)

        # Wizard sections
        self.current_section = WizardSection.objects.get(step=self.step)
        self.current_section.status = IN_PROGRESS_CHOICE
        self.current_section.save()

        next_step_config = get_next_step(ISSUE_TYPES_CHOICE)
        self.next_section = WizardSection.objects.get(step=next_step_config['step'])

    # ---- Access control ----

    def test_redirect_if_not_logged_in(self):
        """Anonymous users should not access the view (404)."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_non_ajax_request_returns_404(self):
        """Non-AJAX requests should return 404 due to AJAXRequestMixin."""
        response = self.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_manager_user_cannot_access(self):
        """Logged-in non GRM manager users should not access the view (404)."""
        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 404)

    # ---- Rendering ----

    def test_get_ajax_request_renders(self):
        """An AJAX GET request should render the formset template with context."""
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn("formset", response.context)
        self.assertEqual(response.context["step"], self.step)
        self.assertEqual(response.context["formset_label"], "Issue Types")
        self.assertEqual(response.context["toast_title"], NOT_PERMITTED_TEXT)
        self.assertEqual(response.context["toast_message"], ITEM_TOAST_ERROR_MESSAGE)

    # ---- Creation logic ----

    def test_post_creates_default_issue_types_when_none_exist(self):
        """Should create the default IssueTypes with empty subtypes if none exist yet."""
        self.assertEqual(IssueType.objects.count(), 0)

        data = {
            "form-TOTAL_FORMS": str(len(DEFAULT_ISSUE_TYPES)),
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }

        # Add each default issue type with at least one subtype
        for i, name in enumerate(DEFAULT_ISSUE_TYPES):
            data[f"form-{i}-name"] = name
            data[f"form-{i}-subtypes"] = f"Subtype {i + 1}"

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))
        self.assertEqual(IssueType.objects.count(), len(DEFAULT_ISSUE_TYPES))

        # Verify each type has its subtype
        for i, name in enumerate(DEFAULT_ISSUE_TYPES):
            issue_type = IssueType.objects.get(name=name)
            self.assertTrue(IssueSubType.objects.filter(parent=issue_type, name=f"Subtype {i + 1}").exists())

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_post_creates_issue_type_with_new_subtypes(self):
        """Should create IssueType with new subtypes."""
        self.assertEqual(IssueType.objects.count(), 0)
        self.assertEqual(IssueSubType.objects.count(), 0)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Complaint",
            "form-0-subtypes": ["Noise", "Water"],
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(IssueType.objects.count(), 1)

        issue_type = IssueType.objects.get(name="Complaint")
        subtypes = IssueSubType.objects.filter(parent=issue_type)
        self.assertEqual(subtypes.count(), 2)
        self.assertSetEqual(set(subtypes.values_list("name", flat=True)), {"Noise", "Water"})

    def test_post_creates_issue_type_with_multiple_subtypes(self):
        """Should create IssueType with multiple new subtypes."""
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Request",
            "form-0-subtypes": ["Information Request", "Service Request", "Document Request"],
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        issue_type = IssueType.objects.get(name="Request")
        self.assertEqual(issue_type.children.count(), 3)

    # ---- Update ----

    def test_post_updates_existing_issue_type(self):
        """Should update an existing IssueType."""
        issue_type = IssueTypeFactory(name="Old Type")
        IssueSubTypeFactory(parent=issue_type, name="Old Subtype")

        updated_name = "Updated Type"

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": issue_type.id,
            "form-0-name": updated_name,
            "form-0-subtypes": ["Updated Subtype"],
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)

        issue_type.refresh_from_db()
        self.assertEqual(issue_type.name, updated_name)

        # Old subtype should be deleted, new one created
        self.assertFalse(IssueSubType.objects.filter(name="Old Subtype").exists())
        self.assertTrue(IssueSubType.objects.filter(parent=issue_type, name="Updated Subtype").exists())

    def test_post_updates_issue_type_adds_new_subtype(self):
        """Should add new subtypes to existing IssueType."""
        issue_type = IssueTypeFactory(name="Grievance")
        existing_subtype = IssueSubTypeFactory(parent=issue_type, name="Existing")

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": issue_type.id,
            "form-0-name": issue_type.name,
            "form-0-subtypes": [existing_subtype.id, "New Subtype"],
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)

        # Should have 2 subtypes now
        self.assertEqual(issue_type.children.count(), 2)
        self.assertTrue(IssueSubType.objects.filter(parent=issue_type, name="Existing").exists())
        self.assertTrue(IssueSubType.objects.filter(parent=issue_type, name="New Subtype").exists())

    def test_post_updates_issue_type_removes_subtype(self):
        """Should remove subtypes from existing IssueType when not selected."""
        issue_type = IssueTypeFactory(name="Feedback")
        subtype1 = IssueSubTypeFactory(parent=issue_type, name="Positive")
        subtype2 = IssueSubTypeFactory(parent=issue_type, name="Negative")

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": issue_type.id,
            "form-0-name": issue_type.name,
            "form-0-subtypes": [subtype1.id],  # Only keep subtype1
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)

        # Only subtype1 should remain
        self.assertEqual(issue_type.children.count(), 1)
        self.assertTrue(IssueSubType.objects.filter(id=subtype1.id).exists())
        self.assertFalse(IssueSubType.objects.filter(id=subtype2.id).exists())

    def test_post_cannot_remove_subtype_with_categories(self):
        """Should not remove subtype if it has associated categories."""
        issue_type = IssueTypeFactory(name="Complaint")
        subtype_in_use = IssueSubTypeFactory(parent=issue_type, name="In Use")
        subtype_free = IssueSubTypeFactory(parent=issue_type, name="Free")

        # Create category linked to subtype_in_use
        IssueCategoryFactory(parent=subtype_in_use)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": issue_type.id,
            "form-0-name": issue_type.name,
            "form-0-subtypes": [subtype_free.id],  # Try to remove subtype_in_use
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)

        # subtype_in_use should still exist because it has categories
        self.assertTrue(IssueSubType.objects.filter(id=subtype_in_use.id).exists())
        self.assertTrue(IssueSubType.objects.filter(id=subtype_free.id).exists())

    # ---- Deletion ----

    def test_post_cannot_delete_restricted_issue_type(self):
        """Should prevent deletion if the IssueType has linked categories."""
        issue_type = IssueTypeFactory(name="Request")
        subtype = IssueSubTypeFactory(parent=issue_type, name="Service")
        IssueCategoryFactory(parent=subtype)  # Creates restricted_deletion=True

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": issue_type.id,
            "form-0-name": issue_type.name,
            "form-0-DELETE": "on",  # marked for deletion
            "form-1-name": "New Type",
            "form-1-subtypes": ["New Subtype"],
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn(
            ITEM_DELETE_ERROR_MESSAGE % {"name": issue_type.name},
            response.context["formset"].non_form_errors()[0],
        )
        self.assertTrue(IssueType.objects.filter(id=issue_type.id).exists())

        # Sections unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_post_can_delete_non_restricted_issue_type(self):
        """Should delete successfully if no linked categories exist."""
        issue_type = IssueTypeFactory(name="Suggestion")
        IssueSubTypeFactory(parent=issue_type, name="Improvement")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": issue_type.id,
            "form-0-name": issue_type.name,
            "form-0-DELETE": "on",  # marked for deletion
            "form-1-name": "Feedback",
            "form-1-subtypes": ["General"],
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))
        self.assertFalse(IssueType.objects.filter(id=issue_type.id).exists())

        # Subtypes should also be deleted
        self.assertFalse(IssueSubType.objects.filter(parent=issue_type).exists())

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_deleting_issue_type_deletes_subtypes(self):
        """Deleting an IssueType should cascade delete its subtypes."""
        issue_type = IssueTypeFactory(name="Question")
        subtype1 = IssueSubTypeFactory(parent=issue_type, name="Technical")
        subtype2 = IssueSubTypeFactory(parent=issue_type, name="General")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": issue_type.id,
            "form-0-name": issue_type.name,
            "form-0-DELETE": "on",
            "form-1-name": "Grievance",
            "form-1-subtypes": ["Noise"],
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(IssueType.objects.filter(id=issue_type.id).exists())
        self.assertFalse(IssueSubType.objects.filter(id=subtype1.id).exists())
        self.assertFalse(IssueSubType.objects.filter(id=subtype2.id).exists())

    # ---- Validation ----

    def test_required_name_field_validation(self):
        """Should return validation errors if 'name' is empty."""
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "",
            "form-0-subtypes": ["Subtype 1"],
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        form = response.context["formset"].forms[0]
        self.assertIn("name", form.errors)
        self.assertEqual(form.errors["name"][0], "This field is required.")

    def test_required_subtypes_field_validation(self):
        """Should return validation errors if 'subtypes' is empty."""
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Complaint",
            "form-0-subtypes": [],
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        form = response.context["formset"].forms[0]
        self.assertIn("subtypes", form.errors)
        self.assertEqual(form.errors["subtypes"][0], "This field is required.")

    def test_duplicate_name_validation_on_create(self):
        """Should raise validation error when creating with a duplicate name."""
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Duplicate Name",
            "form-0-subtypes": ["Sub1"],
            "form-1-name": "Duplicate Name",
            "form-1-subtypes": ["Sub2"],
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(IssueType.objects.count(), 0)
        self.assertEqual(
            response.context["formset"].errors[1]["__all__"][0], "Please correct the duplicate values below."
        )

    def test_duplicate_name_validation_on_update(self):
        """Should raise validation error when updating with a duplicate name."""
        type1 = IssueTypeFactory(name="Type 1")
        IssueSubTypeFactory(parent=type1, name="Sub1")

        type2 = IssueTypeFactory(name="Type 2")
        IssueSubTypeFactory(parent=type2, name="Sub2")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": type1.id,
            "form-0-name": type1.name,
            "form-0-subtypes": ["Sub1"],
            "form-1-id": type2.id,
            "form-1-name": type1.name,  # duplicate
            "form-1-subtypes": ["Sub2"],
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)

        form = response.context["formset"].forms[1]
        self.assertIn("name", form.errors)
        self.assertIn("Issue Type with this Name already exists.", form.errors["name"][0])

        type2.refresh_from_db()
        self.assertEqual(type2.name, "Type 2")

    def test_invalid_form_does_not_update_issue_types(self):
        """Invalid form should not update types or their subtypes."""
        issue_type = IssueTypeFactory(name="Type 1")
        IssueSubTypeFactory(parent=issue_type, name="Sub1")

        type2 = IssueTypeFactory(name="Type 2")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": issue_type.id,
            "form-0-name": " ",  # invalid name
            "form-0-subtypes": ["New Sub"],  # should be ignored
            "form-1-id": type2.id,
            "form-1-name": "New Name",  # should be ignored (no subtypes)
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")

        # No updates applied
        self.assertTrue(IssueType.objects.filter(id=issue_type.id, name="Type 1").exists())
        self.assertTrue(IssueSubType.objects.filter(parent=issue_type, name="Sub1").exists())
        self.assertFalse(IssueSubType.objects.filter(parent=issue_type, name="New Sub").exists())

        self.assertTrue(IssueType.objects.filter(id=type2.id, name="Type 2").exists())

        self.assertFormError(response.context["formset"].forms[0], "name", "This field is required.")
        self.assertFormError(response.context["formset"].forms[1], "subtypes", "This field is required.")

        # Sections remain unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_post_requires_minimum_one_form(self):
        """Should require at least one IssueType form to be valid."""
        IssueTypeFactory()

        data = {
            "form-TOTAL_FORMS": "0",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        formset = response.context["formset"]

        self.assertEqual(IssueType.objects.count(), 1)

        non_form_errors = formset.non_form_errors()
        self.assertTrue(any("at least" in e.lower() or "minimum" in e.lower() for e in non_form_errors))

        self.current_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)

    def test_duplicate_subtype_names_in_same_type(self):
        """Should handle duplicate subtype names within the same type."""
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Complaint",
            "form-0-subtypes": ["Noise", "Noise"],  # Duplicate
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)

        issue_type = IssueType.objects.get(name="Complaint")
        # get_or_create should handle duplicates, only one "Noise" should exist
        self.assertEqual(issue_type.children.filter(name="Noise").count(), 1)
