import pytest
from django.test import TestCase
from django.urls import reverse

from grm.constants import COMPLETED_CHOICE, IN_PROGRESS_CHOICE, NOT_STARTED_CHOICE
from wizard.factories import WizardSectionFactory
from wizard.models import WizardSection


@pytest.mark.django_db
class WizardSectionListViewTest(TestCase):
    """Integration tests for the WizardSectionListView."""

    def setUp(self):
        """Set up test data and URL for each test."""
        self.url = reverse("wizard:wizard_section_list")

        # remove all WizardSections created by the migration
        WizardSection.objects.all().delete()

        # Create test wizard sections
        self.section1 = WizardSectionFactory(status=COMPLETED_CHOICE)
        self.section2 = WizardSectionFactory(status=IN_PROGRESS_CHOICE)
        self.section3 = WizardSectionFactory(status=NOT_STARTED_CHOICE)

    def test_ajax_request_returns_success(self):
        """Test that AJAX requests return successful response."""
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.section1.name)
        self.assertContains(response, self.section2.name)
        self.assertContains(response, self.section3.name)

    def test_non_ajax_request_returns_404(self):
        """Test that non-AJAX requests return 404 due to AJAXRequestMixin."""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_context_contains_wizard_sections(self):
        """Test that the context contains wizard sections with correct name."""
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertIn('wizard_sections', response.context)
        wizard_sections = response.context['wizard_sections']

        # Check all sections are present
        section_names = [section.name for section in wizard_sections]
        self.assertIn(self.section1.name, section_names)
        self.assertIn(self.section2.name, section_names)
        self.assertIn(self.section3.name, section_names)

    def test_wizard_sections_ordering(self):
        """Test that wizard sections are returned in correct order (by id)."""
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        wizard_sections = list(response.context['wizard_sections'])

        # Should be ordered by id (as defined in model Meta)
        self.assertEqual(wizard_sections[0].id, self.section1.id)
        self.assertEqual(wizard_sections[1].id, self.section2.id)
        self.assertEqual(wizard_sections[2].id, self.section3.id)

    def test_template_used(self):
        """Test that the correct template is used."""
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertTemplateUsed(response, 'wizard/wizard_sections.html')

    def test_empty_wizard_sections(self):
        """Test view behavior when no wizard sections exist."""
        WizardSection.objects.all().delete()

        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertIn('wizard_sections', response.context)
        self.assertEqual(len(response.context['wizard_sections']), 0)

    def test_section_with_different_statuses(self):
        """Test that sections with different statuses are all included."""
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        wizard_sections = response.context['wizard_sections']
        statuses = [section.status for section in wizard_sections]

        self.assertIn(COMPLETED_CHOICE, statuses)
        self.assertIn(IN_PROGRESS_CHOICE, statuses)
        self.assertIn(NOT_STARTED_CHOICE, statuses)

    def test_section_fields_in_context(self):
        """Test that all wizard section fields are accessible in context."""
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        wizard_sections = response.context['wizard_sections']
        first_section = wizard_sections.first()

        # Check that all model fields are accessible
        self.assertTrue(hasattr(first_section, 'name'))
        self.assertTrue(hasattr(first_section, 'status'))
        self.assertTrue(hasattr(first_section, 'updated_at'))

    def test_section_with_special_characters(self):
        """Test handling of sections with special characters."""
        section_name = "Section with Special Characters: @#$%^&*()"
        WizardSectionFactory(name=section_name, status=IN_PROGRESS_CHOICE)

        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)

        # Check that special characters are properly escaped in HTML
        # & becomes &amp; in HTML output
        expected_name = "Section with Special Characters: @#$%^&amp;*()"
        self.assertIn(expected_name.encode(), response.content)

        # Also verify the section is in the context with original name
        wizard_sections = response.context['wizard_sections']
        section_names = [section.name for section in wizard_sections]
        self.assertIn(section_name, section_names)

    def test_response_content_type(self):
        """Test that response has correct content type."""
        response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html; charset=utf-8')

    def test_various_ajax_header_formats(self):
        """Test that various AJAX header formats work correctly."""
        # Test with different case variations
        test_headers = [
            'XMLHttpRequest',
            'xmlhttprequest',  # This might not work depending on case sensitivity
        ]

        for header_value in test_headers:
            with self.subTest(header=header_value):
                response = self.client.get(self.url, HTTP_X_REQUESTED_WITH=header_value)
                # Only 'XMLHttpRequest' should work based on the mixin implementation
                if header_value == 'XMLHttpRequest':
                    self.assertEqual(response.status_code, 200)
                else:
                    self.assertEqual(response.status_code, 404)

    def test_post_method_not_allowed(self):
        """Test that POST method returns 405 Method Not Allowed."""
        response = self.client.post(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 405)

    def test_put_method_not_allowed(self):
        """Test that PUT method returns 405 Method Not Allowed."""
        response = self.client.put(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 405)

    def test_delete_method_not_allowed(self):
        """Test that DELETE method returns 405 Method Not Allowed."""
        response = self.client.delete(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 405)

    def test_queryset_efficiency(self):
        """Test that the view doesn't cause unnecessary database queries."""
        with self.assertNumQueries(1):  # Should only need one query to get all sections
            response = self.client.get(self.url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            # Access the wizard_sections to trigger evaluation
            list(response.context['wizard_sections'])
