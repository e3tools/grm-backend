import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from issues.factories import AdministrativeLevelFactory, AdministrativeRegionFactory
from issues.models import AdministrativeRegion


@pytest.mark.django_db
class AdministrativeRegionTest(TestCase):
    """
    Tests for the AdministrativeRegion model and its hierarchical_name logic.
    """

    def setUp(self):
        super().setUp()
        self.level_root = AdministrativeLevelFactory(name="Root Level")
        self.level_child = AdministrativeLevelFactory(name="Child Level")

    def test_only_one_root_region_allowed(self):
        AdministrativeRegionFactory(parent=None, administrative_level=self.level_root)
        with self.assertRaises(ValidationError):
            # Second region with no parent should raise
            region = AdministrativeRegion(
                name="Another Root",
                administrative_level=self.level_root,
                parent=None,
            )
            region.full_clean()
            region.save()

    def test_hierarchical_name_generated_correctly(self):
        root = AdministrativeRegionFactory(name="Root", parent=None, administrative_level=self.level_root)
        child = AdministrativeRegionFactory(name="Child", parent=root, administrative_level=self.level_child)
        grandchild = AdministrativeRegionFactory(name="Grandchild", parent=child, administrative_level=self.level_child)

        self.assertEqual(root.hierarchical_name, "Root")
        # Hierarchical order should be "current, parent, grandparent"
        self.assertEqual(child.hierarchical_name, "Child, Root")
        self.assertEqual(grandchild.hierarchical_name, "Grandchild, Child, Root")

    def test_hierarchical_name_updates_when_parent_changes(self):
        root = AdministrativeRegionFactory(name="Root", parent=None)
        parent1 = AdministrativeRegionFactory(name="ParentA", parent=root, administrative_level=self.level_root)
        parent2 = AdministrativeRegionFactory(name="ParentB", parent=root, administrative_level=self.level_root)
        child = AdministrativeRegionFactory(name="Child", parent=parent1, administrative_level=self.level_child)
        child.parent = parent2
        child.save()

        self.assertIn("ParentB", child.hierarchical_name)
        self.assertNotIn("ParentA", child.hierarchical_name)

    def test_update_children_hierarchy_propagates_to_descendants(self):
        root = AdministrativeRegionFactory(name="Root", parent=None, administrative_level=self.level_root)
        child = AdministrativeRegionFactory(name="Child", parent=root, administrative_level=self.level_child)
        grandchild = AdministrativeRegionFactory(name="Grandchild", parent=child, administrative_level=self.level_child)

        # Change name of parent and save (triggers recursive update)
        child.name = "ChildRenamed"
        child.save()

        grandchild.refresh_from_db()
        # Grandchild's hierarchical_name must reflect new parent name
        self.assertIn("ChildRenamed", grandchild.hierarchical_name)

    def test_str_returns_hierarchical_name(self):
        root = AdministrativeRegionFactory(name="Root", parent=None, administrative_level=self.level_root)
        self.assertEqual(str(root), root.hierarchical_name)

    def test_build_hierarchical_name_method_manual_call(self):
        root = AdministrativeRegionFactory(name="Root", parent=None, administrative_level=self.level_root)
        child = AdministrativeRegionFactory(name="Child", parent=root, administrative_level=self.level_child)
        result = child._build_hierarchical_name()
        self.assertEqual(result, "Child, Root")

    def test_update_hierarchy_flag_skips_rebuild(self):
        root = AdministrativeRegionFactory(name="Root", parent=None, administrative_level=self.level_root)
        child = AdministrativeRegion(name="Child", parent=root, administrative_level=self.level_child)
        child.save(update_hierarchy=False)
        # Since we skipped hierarchy rebuild, field should still be empty string
        self.assertEqual(child.hierarchical_name, "")
