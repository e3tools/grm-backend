from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import ViewTestCase
from issues.factories import IssueStatusFactory
from issues.models import IssueStatus
from wizard.constants import COMPLETED_CHOICE, IN_PROGRESS_CHOICE, ISSUE_STATUS_CHOICE
from wizard.models import WizardSection
from wizard.registry import get_next_step, get_step_by_name


class ResolutionProcessFormViewTest(ViewTestCase):
    """Integration tests for the ResolutionProcessFormView (step 6)."""

    def setUp(self):
        super().setUp()
        self.step = get_step_by_name(ISSUE_STATUS_CHOICE)['step']
        self.url = reverse(f"wizard:setup_step_{self.step}")
        self.user = UserFactory(grm_manager=True)

        # Wizard sections
        self.current_section = WizardSection.objects.get(step=self.step)
        self.current_section.status = IN_PROGRESS_CHOICE
        self.current_section.save()

        next_step_config = get_next_step(ISSUE_STATUS_CHOICE)
        self.next_section = WizardSection.objects.get(step=next_step_config['step'])

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
        IssueStatusFactory.create_batch(4)
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/static_formset.html")
        self.assertIn("formset", response.context)
        self.assertEqual(response.context["step"], self.step)
        self.assertEqual(response.context["formset_label"], "Issue Status")

    def test_post_updates_existing_statuses(self):
        """Submitting valid data should update IssueStatus names."""
        statuses = IssueStatusFactory.create_batch(4)
        updated_names = [f"{s.name} Updated" for s in statuses]

        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "4",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }
        for i, s in enumerate(statuses):
            data.update(
                {
                    f"form-{i}-id": s.id,
                    f"form-{i}-name": updated_names[i],
                }
            )

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))

        for s, expected_name in zip(IssueStatus.objects.all(), updated_names):
            self.assertEqual(s.name, expected_name)

        # Wizard sections should be updated
        self.current_section.refresh_from_db()
        self.next_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)
        self.assertEqual(self.next_section.status, IN_PROGRESS_CHOICE)

    def test_required_fields_validation(self):
        """Should return validation errors when required fields are missing or empty."""
        IssueStatusFactory.create_batch(4)

        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "4",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }

        # Send all names empty
        for i in range(4):
            data.update(
                {
                    f"form-{i}-id": i + 1,
                    f"form-{i}-name": "",
                }
            )

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        formset = response.context["form"]
        for form in formset.forms:
            self.assertIn("name", form.errors)
            self.assertEqual(form.errors["name"][0], "This field is required.")

    def test_post_creates_new_statuses_with_correct_flags(self):
        """Should create new IssueStatus objects with correct flags when none exist initially."""
        self.assertEqual(IssueStatus.objects.count(), 0)

        names = ["initial", "open", "rejected", "final"]
        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }

        for i, name in enumerate(names):
            data.update(
                {
                    f"form-{i}-name": name,
                }
            )

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))

        statuses = IssueStatus.objects.order_by("id")
        self.assertEqual(statuses.count(), 4)

        # Verify that the flags were assigned correctly according to ISSUE_STATUS_DEFINITIONS
        self.assertTrue(statuses[0].initial_status)
        self.assertTrue(statuses[1].open_status)
        self.assertTrue(statuses[2].rejected_status)
        self.assertTrue(statuses[3].final_status)

        for i, status in enumerate(statuses):
            self.assertEqual(status.name, names[i])
