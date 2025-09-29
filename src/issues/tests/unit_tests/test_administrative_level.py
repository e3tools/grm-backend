import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from grm.utils import reset_sequences
from issues.models import AdministrativeLevel


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class AdministrativeLevelTest(TestCase):
    """Unit tests for the AdministrativeLevel model."""

    def setUp(self):
        reset_sequences()
        super().setUp()

    def test_create_administrative_level_success(self):
        """Test successful creation of an AdministrativeLevel instance."""
        level = AdministrativeLevel.objects.create(name="State")

        self.assertIsInstance(level, AdministrativeLevel)
        self.assertEqual(level.name, "State")
        self.assertIsNotNone(level.id)
        self.assertIsNotNone(level.created_date)
        self.assertIsNotNone(level.updated_date)

    def test_name_field_max_length(self):
        """Test that name field respects max_length constraint."""
        long_name = "A" * 256  # Exceeds max_length of 255

        with self.assertRaises(ValidationError):
            level = AdministrativeLevel(name=long_name)
            level.full_clean()

    def test_name_field_required(self):
        """Test that name field is required."""
        level = AdministrativeLevel()

        with self.assertRaises(ValidationError) as cm:
            level.full_clean()

        self.assertIn('name', cm.exception.message_dict)

    def test_name_field_unique_constraint(self):
        """Test that name field has unique constraint."""
        AdministrativeLevel.objects.create(name="Province")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AdministrativeLevel.objects.create(name="Province")

    def test_name_field_case_sensitive_uniqueness(self):
        """Test that name uniqueness is case-sensitive."""
        AdministrativeLevel.objects.create(name="District")

        # Should allow different case
        level = AdministrativeLevel.objects.create(name="DISTRICT")
        self.assertEqual(level.name, "DISTRICT")

    def test_name_field_whitespace_handling(self):
        """Test handling of whitespace in name field."""
        level = AdministrativeLevel.objects.create(name="  County  ")

        # Django doesn't automatically strip whitespace
        self.assertEqual(level.name, "  County  ")

    def test_str_method_returns_name(self):
        """Test that __str__ method returns the name field."""
        level = AdministrativeLevel.objects.create(name="Municipality")

        self.assertEqual(str(level), "Municipality")

    def test_str_method_with_empty_name(self):
        """Test __str__ method behavior with empty name."""
        # Create without validation to test edge case
        level = AdministrativeLevel(name="")

        self.assertEqual(str(level), "")

    def test_created_date_auto_now_add(self):
        """Test that created_date is automatically set on creation."""
        before_creation = timezone.now()
        level = AdministrativeLevel.objects.create(name="Region")
        after_creation = timezone.now()

        self.assertIsNotNone(level.created_date)
        self.assertGreaterEqual(level.created_date, before_creation)
        self.assertLessEqual(level.created_date, after_creation)

    def test_updated_date_auto_now(self):
        """Test that updated_date is automatically updated on save."""
        level = AdministrativeLevel.objects.create(name="Territory")
        original_updated_date = level.updated_date

        # Small delay to ensure different timestamp
        import time

        time.sleep(0.01)

        level.name = "Updated Territory"
        level.save()
        level.refresh_from_db()

        self.assertGreater(level.updated_date, original_updated_date)

    def test_created_date_not_updated_on_save(self):
        """Test that created_date remains unchanged after updates."""
        level = AdministrativeLevel.objects.create(name="Ward")
        original_created_date = level.created_date

        # Small delay to ensure different timestamp
        import time

        time.sleep(0.01)

        level.name = "Updated Ward"
        level.save()
        level.refresh_from_db()

        self.assertEqual(level.created_date, original_created_date)

    def test_verbose_name_singular(self):
        """Test that model has correct singular verbose name."""
        self.assertEqual(AdministrativeLevel._meta.verbose_name, "Administrative Level")

    def test_verbose_name_plural(self):
        """Test that model has correct plural verbose name."""
        self.assertEqual(AdministrativeLevel._meta.verbose_name_plural, "Administrative Levels")

    def test_ordering_by_id(self):
        """Test that model has correct default ordering by id."""
        # Create levels in reverse alphabetical order
        level_z = AdministrativeLevel.objects.create(name="Zone")
        level_a = AdministrativeLevel.objects.create(name="Area")
        level_m = AdministrativeLevel.objects.create(name="Metro")

        # Should be ordered by id (creation order), not name
        levels = list(AdministrativeLevel.objects.all())

        self.assertEqual(levels[0], level_z)  # First created (lowest id)
        self.assertEqual(levels[1], level_a)  # Second created
        self.assertEqual(levels[2], level_m)  # Last created (highest id)

    def test_multiple_instances_creation(self):
        """Test creation of multiple AdministrativeLevel instances."""
        names = ["Federal", "State", "County", "City", "District"]

        for name in names:
            AdministrativeLevel.objects.create(name=name)

        self.assertEqual(AdministrativeLevel.objects.count(), 5)

        # Verify all names are present
        db_names = list(AdministrativeLevel.objects.values_list('name', flat=True))
        for name in names:
            self.assertIn(name, db_names)

    def test_update_existing_instance(self):
        """Test updating an existing AdministrativeLevel instance."""
        level = AdministrativeLevel.objects.create(name="Old Name")
        original_id = level.id
        original_created_date = level.created_date

        level.name = "New Name"
        level.save()
        level.refresh_from_db()

        self.assertEqual(level.id, original_id)
        self.assertEqual(level.name, "New Name")
        self.assertEqual(level.created_date, original_created_date)
        self.assertIsNotNone(level.updated_date)

    def test_delete_instance(self):
        """Test deletion of AdministrativeLevel instance."""
        level = AdministrativeLevel.objects.create(name="To Delete")
        level_id = level.id

        level.delete()

        with self.assertRaises(AdministrativeLevel.DoesNotExist):
            AdministrativeLevel.objects.get(id=level_id)

    def test_field_attributes(self):
        """Test that model fields have correct attributes."""
        name_field = AdministrativeLevel._meta.get_field('name')
        created_date_field = AdministrativeLevel._meta.get_field('created_date')
        updated_date_field = AdministrativeLevel._meta.get_field('updated_date')

        # Name field attributes
        self.assertEqual(name_field.max_length, 255)
        self.assertTrue(name_field.unique)
        self.assertFalse(name_field.blank)
        self.assertFalse(name_field.null)

        # Created date field attributes
        self.assertTrue(created_date_field.auto_now_add)
        self.assertFalse(created_date_field.auto_now)

        # Updated date field attributes
        self.assertTrue(updated_date_field.auto_now)
        self.assertFalse(updated_date_field.auto_now_add)

    def test_unicode_characters_in_name(self):
        """Test that name field supports unicode characters."""
        unicode_name = "Región Metropolitana"
        level = AdministrativeLevel.objects.create(name=unicode_name)

        self.assertEqual(level.name, unicode_name)
        self.assertEqual(str(level), unicode_name)

    def test_special_characters_in_name(self):
        """Test that name field handles special characters."""
        special_name = "Level with Special-Characters & Symbols!"
        level = AdministrativeLevel.objects.create(name=special_name)

        self.assertEqual(level.name, special_name)

    def test_numeric_characters_in_name(self):
        """Test that name field accepts numeric characters."""
        numeric_name = "District 123"
        level = AdministrativeLevel.objects.create(name=numeric_name)

        self.assertEqual(level.name, numeric_name)

    def test_empty_string_name_validation(self):
        """Test validation behavior with empty string name."""
        level = AdministrativeLevel(name="")

        with self.assertRaises(ValidationError):
            level.full_clean()

    def test_none_name_validation(self):
        """Test validation behavior with None name."""
        level = AdministrativeLevel(name=None)

        with self.assertRaises(ValidationError):
            level.full_clean()

    def test_model_representation(self):
        """Test model string representation with various name formats."""
        test_cases = [
            "Simple Name",
            "Name-with-Dashes",
            "Name With Spaces",
            "123 Numeric Start",
            "UPPERCASE",
            "lowercase",
            "MiXeD cAsE",
        ]

        for name in test_cases:
            with self.subTest(name=name):
                level = AdministrativeLevel.objects.create(name=name)
                self.assertEqual(str(level), name)
                level.delete()  # Clean up for next iteration
