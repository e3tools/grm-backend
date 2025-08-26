from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from dashboard.grm.constants import (
    CHOICE_ALERT,
    CHOICE_ANONYMOUS,
    CHOICE_FACILITATOR,
    CHOICE_PHONE,
)
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

    def test_resolution_days_with_resolution_date(self):
        issue = IssueFactory(
            intake_date=timezone.now() - timedelta(days=5),
        )
        issue.resolution_date = timezone.now()
        issue.save()
        self.assertEqual(issue.resolution_days(), 5)

    def test_resolution_days_without_resolution_date(self):
        issue = IssueFactory()
        self.assertIsNone(issue.resolution_days())

    def test_issue_is_created_with_default_contact_medium(self):
        issue = IssueFactory(contact_medium=CHOICE_ANONYMOUS)
        self.assertEqual(issue.contact_medium, CHOICE_ANONYMOUS)

    def test_issue_is_created_with_default_intake_date(self):
        issue = IssueFactory()
        self.assertIsNotNone(issue.intake_date)

    def test_ongoing_issue_default_is_false(self):
        issue = IssueFactory()
        self.assertFalse(issue.ongoing_issue)

    def test_automatic_tracking_code_generation(self):
        issue = IssueFactory()
        self.assertIsNotNone(issue.tracking_code)

    def test_contact_method_is_required_for_channel_alert_medium(self):
        with self.assertRaises(ValidationError):
            IssueFactory(contact_medium=CHOICE_ALERT, contact_method=None)

    def test_valid_issue_saves_correctly(self):
        issue = IssueFactory(
            contact_medium=CHOICE_FACILITATOR, contact_method=CHOICE_PHONE, contact_information="1234567890"
        )
        try:
            issue.full_clean()
            issue.save()
        except ValidationError:
            self.fail("ValidationError was raised on a valid model instance.")

    def test_full_clean_is_called_on_save(self):
        issue = IssueFactory.build(contact_medium=CHOICE_ALERT, contact_method=None)
        with self.assertRaises(ValidationError):
            issue.save()
