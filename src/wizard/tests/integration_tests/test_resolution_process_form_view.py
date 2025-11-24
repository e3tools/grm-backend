from django.test import override_settings
from django.urls import reverse

from authentication.factories import UserFactory
from grm.tests.base import ViewTestCase
from issues.factories import IssueStatusFactory
from issues.models import IssueStatus
from wizard.constants import COMPLETED_CHOICE, IN_PROGRESS_CHOICE, ISSUE_STATUS_CHOICE
from wizard.models import WizardSection
from wizard.registry import get_next_step, get_step_by_name


@override_settings(LANGUAGE_CODE='en-us')
class ResolutionProcessFormViewTest(ViewTestCase):
    """Integration tests for the ResolutionProcessFormView."""

    def setUp(self):
        super().setUp()
        self.step = get_step_by_name(ISSUE_STATUS_CHOICE)['step']
        self.url = reverse(f"wizard:setup_step_{self.step}")
        self.user = UserFactory(grm_owner=True)

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

    def test_logged_in_non_grm_owner_user_cannot_access(self):
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

        # Ensure threshold_days field present for non-final/rejected rows
        formset = response.context["form"]
        # find a form that corresponds to a non-final/non-rejected flag (initial/open)
        found_threshold = any('threshold_days' in f.fields for f in formset.forms)
        self.assertTrue(found_threshold)

    def test_post_updates_existing_statuses_including_thresholds(self):
        """Submitting valid data should update IssueStatus names and threshold_days."""
        statuses = IssueStatusFactory.create_batch(4)
        updated_names = [f"{s.name} Updated" for s in statuses]
        updated_thresholds = [s.threshold_days + 2 for s in statuses]

        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "4",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }
        for i, s in enumerate(statuses):
            # Always include id and name
            data.update(
                {
                    f"form-{i}-id": s.id,
                    f"form-{i}-name": updated_names[i],
                }
            )
            # threshold_days may be absent for rejected/final; only include if field exists on form
            # In the existing DB rows, flags determine which row is which; we include threshold for rows
            # that are not rejected/final to simulate realistic update.
            if not (s.rejected_status or s.final_status):
                data[f"form-{i}-threshold_days"] = updated_thresholds[i]

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))

        # Refresh and assert names and thresholds updated where applicable
        for s in IssueStatus.objects.order_by("id"):
            idx = list(statuses).index(next(x for x in statuses if x.id == s.id))
            self.assertEqual(s.name, updated_names[idx])
            if not (s.rejected_status or s.final_status):
                self.assertEqual(s.threshold_days, updated_thresholds[idx])

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

        # Send all names empty; include threshold_days for non-final/rejected forms to simulate real payload
        for i in range(4):
            data.update(
                {
                    f"form-{i}-id": i + 1,
                    f"form-{i}-name": "",
                }
            )
            # include a valid threshold for completeness (if field present)
            data[f"form-{i}-threshold_days"] = "2"

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        formset = response.context["form"]
        for form in formset.forms:
            self.assertIn("name", form.errors)
            self.assertEqual(form.errors["name"][0], "This field is required.")

    def test_threshold_validation_rejects_zero(self):
        """threshold_days clean method should reject zero values for applicable forms."""
        IssueStatusFactory.create_batch(4)

        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "4",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }

        # For the first form (initial_status) set threshold to 0 to trigger validation error
        data.update(
            {
                "form-0-id": IssueStatus.objects.all().order_by("id")[0].id,
                "form-0-name": "New name",
                "form-0-threshold_days": "0",
            }
        )
        # Fill remaining forms with valid values
        for i in range(1, 4):
            inst = IssueStatus.objects.all().order_by("id")[i]
            data.update(
                {
                    f"form-{i}-id": inst.id,
                    f"form-{i}-name": inst.name,
                    f"form-{i}-threshold_days": str(inst.threshold_days or 1),
                }
            )

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 200)
        formset = response.context["form"]
        # The first form should have threshold_days error
        first_form = formset.forms[0]
        self.assertIn("threshold_days", first_form.errors)
        self.assertTrue(any("greater than zero" in str(e).lower() for e in first_form.errors["threshold_days"]))

    def test_post_creates_new_statuses_with_correct_flags_and_thresholds(self):
        """Should create new IssueStatus objects with correct flags and threshold_days when none exist initially."""
        # Ensure no statuses exist
        IssueStatus.objects.all().delete()
        self.assertEqual(IssueStatus.objects.count(), 0)

        # Names and thresholds for the new forms. For rejected/final we must not send threshold_days (field removed)
        names = ["initial", "open", "rejected", "final"]
        thresholds = ["3", "5"]  # only for initial and open

        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "1",
            "form-MAX_NUM_FORMS": "100",
        }

        # Fill data: include threshold for first two forms only
        for i, name in enumerate(names):
            data[f"form-{i}-name"] = name
            if i < len(thresholds):
                data[f"form-{i}-threshold_days"] = thresholds[i]

        response = self.post(self.url, data, ajax=True)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse(f"wizard:setup_step_{self.step + 1}"))

        statuses = IssueStatus.objects.order_by("id")
        self.assertEqual(statuses.count(), 4)

        # Verify flags according to ISSUE_STATUS_DEFINITIONS order
        self.assertTrue(statuses[0].initial_status)
        self.assertTrue(statuses[1].open_status)
        self.assertTrue(statuses[2].rejected_status)
        self.assertTrue(statuses[3].final_status)

        # Check thresholds: first two should have the provided values; rejected/final use default (model default)
        self.assertEqual(statuses[0].threshold_days, int(thresholds[0]))
        self.assertEqual(statuses[1].threshold_days, int(thresholds[1]))
        # rejected and final should keep default (1) because threshold field was not provided
        self.assertEqual(statuses[2].threshold_days, IssueStatus._meta.get_field('threshold_days').default)
        self.assertEqual(statuses[3].threshold_days, IssueStatus._meta.get_field('threshold_days').default)
