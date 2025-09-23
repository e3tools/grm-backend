import pytest
from django.test import TestCase
from django.urls import reverse

from authentication.factories import UserFactory
from wizard.factories import WizardSectionFactory
from wizard.models import WizardSection


@pytest.mark.django_db
class CustomizationWizardViewTest(TestCase):
    """Integration tests for the CustomizationWizardView."""

    def setUp(self):
        self.url = reverse("wizard:customization_wizard")
        self.user = UserFactory(username="testuser", password="testpass", grm_manager=True)

    def test_redirect_if_not_logged_in(self):
        """Test to make the view return 404 to anonymous users."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_logged_in_user_can_access(self):
        """Test that logged-in users can access the view."""
        self.client.login(username="testuser", password="testpass")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "wizard/grm_customization.html")

    def test_context_total_steps_with_sections(self):
        """Test that total_steps reflects the number of WizardSections."""
        self.client.login(username="testuser", password="testpass")

        # Remove all WizardSections created by the migration
        WizardSection.objects.all().delete()

        WizardSectionFactory.create_batch(5)
        response = self.client.get(self.url)

        self.assertEqual(response.context["total_steps"], 5)
