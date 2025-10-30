from django.urls import reverse

from authentication.factories import UserFactory
from grm.constants import (
    COMPLETED_CHOICE,
    DEPARTMENT_DELETE_ERROR_MESSAGE,
    DEPARTMENT_TOAST_ERROR_MESSAGE,
    IN_PROGRESS_CHOICE,
    NOT_PERMITTED_TEXT,
    NOT_STARTED_CHOICE,
)
from grm.tests.base import ViewTestCase
from issues.factories import (
    AdministrativeLevelFactory,
    IssueCategoryFactory,
    IssueDepartmentAdministrativeLevelFactory,
    IssueDepartmentFactory,
)
from issues.models import IssueDepartment, IssueDepartmentAdministrativeLevel
from wizard.models import WizardSection


class IssueDepartmentsFormViewTest(ViewTestCase):
    """Integration tests for the IssueDepartmentsFormView with IssueDepartmentForm + administrative_levels."""

    def setUp(self):
        super().setUp()
        self.url = reverse("wizard:setup_step_4")
        self.user = UserFactory(grm_manager=True)

        # Wizard sections
        self.current_section = WizardSection.objects.get(id=4)
        WizardSection.objects.filter(id=4).update(status=IN_PROGRESS_CHOICE)
        self.next_section = WizardSection.objects.get(id=5)

        # Administrative levels for use in tests
        self.level1 = AdministrativeLevelFactory()
        self.level2 = AdministrativeLevelFactory()

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

    def test_get_ajax_request_renders(self):
        """An AJAX GET request should render the formset template with context."""
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn("formset", response.context)
        self.assertEqual(response.context["step"], 4)
        self.assertEqual(response.context["formset_label"], "Departments")
        self.assertEqual(response.context["toast_title"], NOT_PERMITTED_TEXT)
        self.assertEqual(response.context["toast_message"], DEPARTMENT_TOAST_ERROR_MESSAGE)
        self.assertTrue(response.context["two_fields_by_row"])

    def test_post_creates_new_issue_department(self):
        """Submitting valid data should create a new IssueDepartment with selected administrative levels."""
        self.assertEqual(IssueDepartment.objects.count(), 0)

        department_name = "Department 1"
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": department_name,
            "form-0-administrative_levels": [self.level1.id, self.level2.id],
        }
        response = self.post(self.url, data, ajax=True)

        # Expect redirect to next wizard step
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_5"))

        # Department created with both levels
        department = IssueDepartment.objects.get(name=department_name)
        self.assertSetEqual(
            set(
                IssueDepartmentAdministrativeLevel.objects.filter(department=department).values_list(
                    "administrative_level", flat=True
                )
            ),
            {self.level1.id, self.level2.id},
        )

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_post_updates_existing_issue_department(self):
        """Updating an existing IssueDepartment should also update its administrative levels."""
        department = IssueDepartmentFactory(name="Old Department")
        IssueDepartmentAdministrativeLevelFactory(department=department, administrative_level=self.level1)

        department_name = "Updated Department"
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": department.id,
            "form-0-name": department_name,
            "form-0-administrative_levels": [self.level2.id],  # replace level1 with level2
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        department.refresh_from_db()
        self.assertEqual(department.name, department_name)
        self.assertSetEqual(
            set(
                IssueDepartmentAdministrativeLevel.objects.filter(department=department).values_list(
                    "administrative_level", flat=True
                )
            ),
            {self.level2.id},
        )

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_invalid_form_does_not_update_issue_departments(self):
        """Invalid form should not update departments or their administrative levels."""
        department = IssueDepartmentFactory(name="department1")
        IssueDepartmentAdministrativeLevelFactory(department=department, administrative_level=self.level1)
        department2 = IssueDepartmentFactory(name="department2")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": department.id,
            "form-0-name": " ",  # invalid name
            "form-0-administrative_levels": [self.level2.id],  # should be ignored
            "form-1-id": department2.id,
            "form-1-name": "New name",  # should be ignored
        }
        response = self.post(self.url, data, ajax=True)

        # Expect re-render (200) with errors
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")

        # No updates applied
        self.assertTrue(IssueDepartment.objects.filter(id=department.id, name=department.name).exists())
        self.assertSetEqual(
            set(
                IssueDepartmentAdministrativeLevel.objects.filter(department=department).values_list(
                    "administrative_level", flat=True
                )
            ),
            {self.level1.id},  # still level1, not replaced by level2
        )
        self.assertTrue(IssueDepartment.objects.filter(id=department2.id, name=department2.name).exists())

        self.assertFormError(response.context["formset"].forms[0], "name", "This field is required.")
        self.assertFormError(response.context["formset"].forms[1], "administrative_levels", "This field is required.")

        # Sections remain unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_duplicate_name_validation_on_create(self):
        """Creating with a duplicate department name should re-render with error."""
        department = IssueDepartmentFactory()

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": department.id,
            "form-0-name": department.name,
            "form-0-administrative_levels": [self.level1.id],
            "form-1-name": department.name,  # duplicate
            "form-1-administrative_levels": [self.level2.id],  # should be ignored
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertEqual(IssueDepartment.objects.count(), 1)
        self.assertFormError(
            response.context["formset"].forms[1], "name", 'Issue Department with this Name already exists.'
        )

        # Sections unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_duplicate_name_validation_on_update(self):
        """Updating to a duplicate department name should re-render with error."""
        department = IssueDepartmentFactory(name="department1")
        department2 = IssueDepartmentFactory(name="department2")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": department.id,
            "form-0-name": department.name,
            "form-1-id": department2.id,
            "form-1-name": department.name,  # duplicate
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertTrue(IssueDepartment.objects.filter(id=department.id, name=department.name).exists())
        self.assertTrue(IssueDepartment.objects.filter(id=department2.id, name=department2.name).exists())

        # Sections unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_post_cannot_delete_restricted_department(self):
        """Deleting should fail if restricted_deletion=True (related IssueCategory exists)."""
        department = IssueDepartmentFactory(name="Restricted Department")
        assigned_department = IssueDepartmentAdministrativeLevelFactory(department=department)
        IssueCategoryFactory(assigned_department=assigned_department)  # generates restricted_deletion=True

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": department.id,
            "form-0-name": department.name,
            "form-0-DELETE": "on",  # marked for deletion
            "form-1-name": "new",
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/formset.html")
        self.assertIn(
            DEPARTMENT_DELETE_ERROR_MESSAGE % {"name": department.name},
            response.context["formset"].non_form_errors()[0],
        )
        self.assertTrue(IssueDepartment.objects.filter(id=department.id, name=department.name).exists())

        # Sections unchanged
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
        self.assertEqual(self.next_section.status, NOT_STARTED_CHOICE)

    def test_post_can_delete_non_restricted_department(self):
        """Deleting should succeed if restricted_deletion=False."""
        department = IssueDepartmentFactory(name="Free Department")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": department.id,
            "form-0-name": department.name,
            "form-0-DELETE": "on",  # marked for deletion
            "form-1-name": "new",
            "form-1-administrative_levels": [self.level1.id],
        }
        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_5"))
        self.assertFalse(IssueDepartment.objects.filter(id=department.id).exists())

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_post_requires_minimum_one(self):
        """
        Should require at least one IssueDepartment form to be valid.
        """
        IssueDepartmentFactory()

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
        self.assertEqual(IssueDepartment.objects.count(), 1)

        # Verify formset validation error due to min_num constraint
        non_form_errors = formset.non_form_errors()
        self.assertTrue(any("at least" in e.lower() or "minimum" in e.lower() for e in non_form_errors))

        # Wizard should stay in current section (not mark completed)
        self.current_section.refresh_from_db()
        self.assertEqual(self.current_section.status, IN_PROGRESS_CHOICE)
