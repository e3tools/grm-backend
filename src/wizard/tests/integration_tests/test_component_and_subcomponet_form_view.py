from django.urls import reverse

from authentication.factories import UserFactory
from grm.constants import (
    COMPLETED_CHOICE,
    COMPONENT_DELETE_ERROR_MESSAGE,
    COMPONENT_REQUIRED_ERROR_MESSAGE,
    COMPONENT_TOAST_ERROR_MESSAGE,
    IN_PROGRESS_CHOICE,
    NOT_PERMITTED_TEXT,
    SUBCOMPONENT_DELETE_ERROR_MESSAGE,
    SUBCOMPONENT_REQUIRED_ERROR_MESSAGE,
)
from grm.tests.base import ViewTestCase
from issues.factories import ComponentFactory, IssueFactory, SubComponentFactory
from issues.models import Component, SubComponent
from wizard.models import WizardSection


class ComponentAndSubComponentFormViewTest(ViewTestCase):
    """Integration tests for the ComponentAndSubComponentFormView (step 9)."""

    def setUp(self):
        super().setUp()
        self.url = reverse("wizard:setup_step_9")
        self.user = UserFactory(grm_manager=True)

        self.current_section = WizardSection.objects.get(id=9)
        WizardSection.objects.filter(id=9).update(status=IN_PROGRESS_CHOICE)
        self.next_section = WizardSection.objects.get(id=10)

    def test_redirect_if_not_logged_in(self):
        """Anonymous users should get a 404."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_non_ajax_request_returns_404(self):
        """Non-AJAX requests should return 404."""
        response = self.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_manager_user_cannot_access(self):
        """Non-GRM manager users should not access the view."""
        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_get_ajax_request_renders(self):
        """View should render correctly with expected context."""
        response = self.get(self.url, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/nested_formset.html")

        context = response.context
        self.assertIn("formset", context)
        self.assertEqual(context["step"], 9)
        self.assertEqual(context["formset_label"], "Components and Subcomponents")
        self.assertEqual(context["toast_title"], NOT_PERMITTED_TEXT)
        self.assertEqual(context["toast_message"], COMPONENT_TOAST_ERROR_MESSAGE)

    def test_post_creates_component_with_subcomponent(self):
        """Submitting valid data should create a Component and its SubComponent."""
        self.assertEqual(Component.objects.count(), 0)
        self.assertEqual(SubComponent.objects.count(), 0)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Main Component",
            "form-0-description": "Description",
            # Subcomponent inline
            "subcomponent_form-0-TOTAL_FORMS": "1",
            "subcomponent_form-0-INITIAL_FORMS": "0",
            "subcomponent_form-0-MIN_NUM_FORMS": "0",
            "subcomponent_form-0-MAX_NUM_FORMS": "100",
            "subcomponent_form-0-0-name": "Sub One",
            "subcomponent_form-0-0-description": "Sub desc",
        }

        response = self.post(self.url, data, ajax=True)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("wizard:setup_step_10"))
        self.assertEqual(Component.objects.count(), 1)
        self.assertEqual(SubComponent.objects.count(), 1)

        component = Component.objects.first()
        sub = SubComponent.objects.first()
        self.assertEqual(sub.parent, component)

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_post_updates_existing_component(self):
        """Updating an existing Component should succeed."""
        component = ComponentFactory(name="Old Component")
        sub = SubComponentFactory(parent=component, name="Old Sub")

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": component.id,
            "form-0-name": "Updated Component",
            "form-0-description": "Updated description",
            "subcomponent_form-0-TOTAL_FORMS": "1",
            "subcomponent_form-0-INITIAL_FORMS": "1",
            "subcomponent_form-0-MIN_NUM_FORMS": "0",
            "subcomponent_form-0-MAX_NUM_FORMS": "100",
            "subcomponent_form-0-0-id": sub.id,
            "subcomponent_form-0-0-name": "Updated Sub",
            "subcomponent_form-0-0-description": "Updated sub description",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)

        component.refresh_from_db()
        sub.refresh_from_db()
        self.assertEqual(component.name, "Updated Component")
        self.assertEqual(sub.name, "Updated Sub")

    def test_post_without_subcomponent(self):
        """Should raise validation error because at least one subcomponent is required."""
        component = ComponentFactory(name="Old Component")

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": component.id,
            "form-0-name": "Updated Component",
            "form-0-description": "Updated description",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)

        self.assertIn(SUBCOMPONENT_REQUIRED_ERROR_MESSAGE, response.context['formset'].subformsets[0].non_form_errors())

        component.refresh_from_db()
        self.assertEqual(component.name, "Old Component")

    def test_post_can_delete_components_but_not_all(self):
        """Deletes the selected components but does not allow deleting all."""
        components = ComponentFactory.create_batch(2)
        self.assertEqual(Component.objects.count(), 2)

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": components[0].id,
            "form-0-name": components[0].name,
            "form-0-description": components[0].description,
            "form-0-DELETE": "on",
            "form-1-id": components[1].id,
            "form-1-name": components[1].name,
            "form-1-description": components[1].description,
            "subcomponent_form-0-TOTAL_FORMS": "1",
            "subcomponent_form-0-INITIAL_FORMS": "0",
            "subcomponent_form-0-MIN_NUM_FORMS": "0",
            "subcomponent_form-0-MAX_NUM_FORMS": "100",
            "subcomponent_form-0-0-name": "name",
            "subcomponent_form-0-0-description": "description",
            "subcomponent_form-1-TOTAL_FORMS": "1",
            "subcomponent_form-1-INITIAL_FORMS": "0",
            "subcomponent_form-1-MIN_NUM_FORMS": "0",
            "subcomponent_form-1-MAX_NUM_FORMS": "100",
            "subcomponent_form-1-0-name": "name",
            "subcomponent_form-1-0-description": "description",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Component.objects.count(), 1)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": components[1].id,
            "form-0-name": components[1].name,
            "form-0-description": components[1].description,
            "form-0-DELETE": "on",
            "subcomponent_form-0-TOTAL_FORMS": "1",
            "subcomponent_form-0-INITIAL_FORMS": "0",
            "subcomponent_form-0-MIN_NUM_FORMS": "0",
            "subcomponent_form-0-MAX_NUM_FORMS": "100",
            "subcomponent_form-0-0-name": "name",
            "subcomponent_form-0-0-description": "description",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Component.objects.count(), 1)

        self.assertIn(COMPONENT_REQUIRED_ERROR_MESSAGE, response.context['formset'].non_form_errors())

    def test_cannot_delete_component_in_use(self):
        """Should raise validation error when deleting a component referenced by an Issue."""
        component = ComponentFactory()
        IssueFactory(component=component)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": component.id,
            "form-0-name": component.name,
            "form-0-description": component.description,
            "form-0-DELETE": "on",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            COMPONENT_DELETE_ERROR_MESSAGE % {'name': component.name}, response.context['formset'].non_form_errors()
        )

        self.assertEqual(Component.objects.count(), 1)

    def test_cannot_delete_subcomponent_in_use(self):
        """Should raise validation error when deleting a SubComponent referenced by an Issue."""
        component = ComponentFactory()
        sub = SubComponentFactory(parent=component)
        IssueFactory(sub_component=sub)

        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": component.id,
            "form-0-name": component.name,
            "form-0-description": component.description,
            "subcomponent_form-0-TOTAL_FORMS": "1",
            "subcomponent_form-0-INITIAL_FORMS": "1",
            "subcomponent_form-0-MIN_NUM_FORMS": "0",
            "subcomponent_form-0-MAX_NUM_FORMS": "100",
            "subcomponent_form-0-0-id": sub.id,
            "subcomponent_form-0-0-name": sub.name,
            "subcomponent_form-0-0-description": sub.description,
            "subcomponent_form-0-0-DELETE": "on",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            SUBCOMPONENT_DELETE_ERROR_MESSAGE % {'name': sub.name},
            response.context['formset'].subformsets[0].non_form_errors(),
        )

    def test_duplicate_name_validation_on_create(self):
        """Should raise validation error when creating components with duplicate names."""
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-name": "Duplicate",
            "form-0-description": "First",
            "form-1-name": "Duplicate",
            "form-1-description": "Second",
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Component.objects.count(), 0)

        self.assertEqual(response.context["form"].errors[1]["__all__"][0], "Please correct the duplicate values below.")

    def test_duplicate_name_validation_on_update(self):
        """Should raise validation error when updating with a duplicate name."""
        c1 = ComponentFactory(name="CompA")
        c2 = ComponentFactory(name="CompB")

        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "100",
            "form-0-id": c1.id,
            "form-0-name": c1.name,
            "form-0-description": c1.description,
            "form-1-id": c2.id,
            "form-1-name": c1.name,  # duplicate
            "form-1-description": c2.description,
        }

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)

        form = response.context["form"].forms[1]
        self.assertIn("name", form.errors)
        self.assertIn("Component with this Name already exists.", form.errors["name"][0])

        c2.refresh_from_db()
        self.assertEqual(c2.name, "CompB")
