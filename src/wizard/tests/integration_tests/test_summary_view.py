from django.contrib.messages import get_messages
from django.urls import reverse

from authentication.factories import UserFactory
from grm.constants import (
    COMPLETED_CHOICE,
    IN_PROGRESS_CHOICE,
    MAP_WIZARD_SECTION,
    SUMMARY_DISPLAY,
)
from grm.tests.base import ViewTestCase
from wizard.models import WizardSection


class SummaryViewTest(ViewTestCase):
    """Integration tests for the SummaryView (step 10)."""

    def setUp(self):
        """Set up the test environment for the summary step."""
        super().setUp()
        self.url = reverse("wizard:setup_step_10")
        self.user = UserFactory(grm_manager=True)

        self.current_section = WizardSection.objects.get(id=10)

    def test_redirect_if_not_logged_in(self):
        """Anonymous users should receive 404."""
        response = self.get(self.url, authorized=False, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_non_ajax_request_returns_404(self):
        """Non-AJAX requests should return 404."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_non_grm_manager_user_cannot_access(self):
        """Non GRM manager users should not access this step."""
        self.user = UserFactory()
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 404)

    def test_get_ajax_request_renders_successfully(self):
        """GET AJAX request should render successfully with correct context."""
        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/summary.html")

        # Context assertions
        self.assertEqual(response.context["step"], 10)
        self.assertEqual(response.context["card_title"], SUMMARY_DISPLAY)
        self.assertTrue(response.context["disabled_submit"])
        self.assertIsInstance(response.context["summary"], list)

    def test_disabled_submit_true_when_previous_steps_incomplete(self):
        """Submit button should be disabled when any section before step 10 is incomplete."""
        WizardSection.objects.filter(id__lt=self.current_section.id).update(status=IN_PROGRESS_CHOICE)

        response = self.get(self.url, ajax=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["disabled_submit"])

    def test_disabled_submit_false_when_all_previous_steps_are_completed(self):
        """Submit button should be enabled when all previous steps are completed."""
        self.assertNotEqual(self.current_section.status, COMPLETED_CHOICE)

        WizardSection.objects.filter(id__lt=self.current_section.id).update(status=COMPLETED_CHOICE)
        response = self.get(self.url, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["disabled_submit"])

    def test_post_completes_wizard_when_all_steps_done(self):
        """POST request should mark setup as complete when all sections are completed."""
        WizardSection.objects.update(status=COMPLETED_CHOICE)
        response = self.post(self.url, {}, ajax=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

        data = response.json()
        self.assertEqual(data["redirect_url"], reverse("dashboard:diagnostics:home"))

        # Verify last section updated correctly
        self.current_section.refresh_from_db()
        self.assertEqual(self.current_section.status, COMPLETED_CHOICE)

    def test_post_fails_if_previous_steps_incomplete(self):
        """POST should not complete wizard if earlier steps are incomplete."""
        WizardSection.objects.filter(id__lt=self.current_section.id).update(status=IN_PROGRESS_CHOICE)

        response = self.post(self.url, {}, ajax=True)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should not redirect
        self.assertIsNone(data.get("redirect_url"))

        # Error message in Django messages framework
        messages = [m.message for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("cannot be completed" in m for m in messages))

    def test_post_non_ajax_returns_404(self):
        """Non-AJAX POST should return 404."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_response_content_type(self):
        """GET should return correct content type."""
        response = self.get(self.url, ajax=True)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

    def test_post_response_content_type(self):
        """POST should return correct content type (JSON)."""
        WizardSection.objects.update(status=COMPLETED_CHOICE)
        response = self.post(self.url, {}, ajax=True)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_summary_contains_all_previous_sections(self):
        """Summary should list all previous wizard sections."""
        response = self.get(self.url, ajax=True)
        summary_data = response.context["summary"]

        section_names = [s["title"] for s in summary_data]
        db_section_names = list(WizardSection.objects.values_list("name", flat=True))[:-1]
        db_section_names = [MAP_WIZARD_SECTION.get(name) for name in db_section_names]

        self.assertCountEqual(section_names, db_section_names)
