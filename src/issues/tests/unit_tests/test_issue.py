from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from gevent.testing import TestCase

from grm.utils import reset_sequences
from issues.factories import IssueFactory


@pytest.mark.django_db
class TestIssue(TestCase):
    """
    Tests for the custom methods and properties of the Issue model.
    """

    def setUp(self):
        reset_sequences()
        super().setUp()

    def test_str_representation(self):
        """
        Tests that the __str__ method returns the correct string format.
        """
        issue = IssueFactory()
        expected_str = (
            f"{issue.status.name} - {issue.category.name} - {issue.issue_type.name} "
            f"({issue.intake_date.strftime('%Y-%m-%d %H:%M')})"
        )
        self.assertEqual(str(issue), expected_str)

    def test_resolution_days_with_resolution_date(self):
        """
        Tests the resolution_days method when the issue is resolved.
        """
        issue = IssueFactory(intake_date=timezone.now() - timedelta(days=5))
        issue.resolution_date = timezone.now()
        issue.save()
        self.assertEqual(issue.resolution_days(), 5)

    def test_resolution_days_without_resolution_date(self):
        """
        Tests the resolution_days method when the issue is not resolved.
        """
        issue = IssueFactory()
        self.assertIsNone(issue.resolution_days())

    def test_issue_is_created_with_default_contact_medium(self):
        """
        Tests that an Issue is created with the correct default contact_medium.
        """
        issue = IssueFactory(contact_medium='channel-alert')
        self.assertEqual(issue.contact_medium, 'channel-alert')

    def test_issue_is_created_with_default_intake_date(self):
        """
        Tests that an Issue is created with a default intake_date set to now.
        """
        issue = IssueFactory()
        self.assertIsNotNone(issue.intake_date)

    def test_ongoing_issue_default_is_false(self):
        """
        Tests that the ongoing_issue field defaults to False.
        """
        issue = IssueFactory()
        self.assertFalse(issue.ongoing_issue)

    def test_automatic_tracking_code_generation(self):
        """
        Tests that the tracking_code is automatically populated upon saving.
        """
        issue = IssueFactory()
        self.assertIsNotNone(issue.tracking_code)

    def test_updated_date_updates_on_save(self):
        """
        Tests that the updated_date field updates on subsequent saves.
        """
        issue = IssueFactory()
        initial_updated_date = issue.updated_date
        issue.title = "A new title"
        issue.save()
        self.assertGreater(issue.updated_date, initial_updated_date)

    def test_contact_method_is_required_for_non_channel_alert_medium(self):
        """
        Tests that a ValidationError is raised if contact_medium is not 'channel-alert'
        and contact_method is not provided.
        """
        with self.assertRaises(ValidationError) as cm:
            IssueFactory(contact_medium='facilitator', contact_method=None)
            self.assertIn(
                "You must define the contact method is your contact medium is not channel alert", str(cm.exception)
            )

    def test_contact_information_is_valid_for_email_method(self):
        """
        Tests that a ValidationError is raised if contact_method is 'email' but
        contact_information is not a valid email address.
        """
        with self.assertRaises(ValidationError) as cm:
            IssueFactory(
                contact_method='email',
                contact_information='not_an_email',
            )
            self.assertIn("If email contact method is selected provide a valid email", str(cm.exception))

    def test_contact_information_is_valid_for_non_email_method(self):
        """
        Tests that a ValidationError is raised if contact_method is not 'email' but
        contact_information is a valid email address.
        """
        with self.assertRaises(ValidationError) as cm:
            IssueFactory(
                contact_method='phone_number',
                contact_information='valid_email@example.com',
            )
            self.assertIn(
                "If phone or whatsapp contact method is selected provide a valid phone number", str(cm.exception)
            )

    def test_valid_issue_saves_correctly(self):
        """
        Tests that an issue with valid data saves without raising errors.
        """
        issue = IssueFactory(
            contact_medium='facilitator',
            contact_method='phone_number',
            contact_information='1234567890',
        )
        try:
            issue.full_clean()
            issue.save()
        except ValidationError:
            self.fail("ValidationError was raised on a valid model instance.")

    def test_full_clean_is_called_on_save(self):
        """
        Tests that the _validate_contact_method_based_on_contact_medium method
        is called during the save process.
        """
        issue = IssueFactory.build(contact_medium='facilitator', contact_method=None)
        with self.assertRaises(ValidationError):
            issue.save()
