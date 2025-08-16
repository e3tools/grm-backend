from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from gevent.testing import TestCase

from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueFactory,
    IssueStatusFactory,
    IssueTypeFactory,
    UserFactory,
)

# Importa los modelos directamente, ya que se gestionarán manualmente
from issues.models import (
    AdministrativeLevel,
    IssueDepartment,
    IssueDepartmentAdministrativeLevel,
)


@pytest.mark.django_db
class TestIssue(TestCase):
    """
    Tests for the custom methods and properties of the Issue model.
    """

    @classmethod
    def setUpClass(cls):
        """
        Setup de la clase, se ejecuta una sola vez.
        Crea las dependencias de datos que serán compartidas por todos los tests.
        """
        super().setUpClass()
        # Nivel administrativo
        cls.administrative_level = AdministrativeLevel.objects.get_or_create(name="Country")[0]

        # Regiones administrativas
        cls.root_region = AdministrativeRegionFactory(
            name="Root Region",
            administrative_level=cls.administrative_level,
            parent=None,
        )
        cls.child_region = AdministrativeRegionFactory(
            name="Child Region",
            administrative_level=cls.administrative_level,
            parent=cls.root_region,
        )

        # Departamentos y relaciones
        cls.department = IssueDepartment.objects.get_or_create(name="Test Department")[0]
        cls.department_admin_level = IssueDepartmentAdministrativeLevel.objects.get_or_create(
            department=cls.department, administrative_level=cls.administrative_level
        )[0]

        # Categoría
        cls.category = IssueCategoryFactory(
            name="Test Category",
            assigned_department=cls.department_admin_level,
            assigned_appeal_department=cls.department_admin_level,
            assigned_escalation_department=cls.department_admin_level,
        )

        # Tipo de problema, estado y usuarios
        cls.issue_type = IssueTypeFactory(name="Test Issue Type")
        cls.status = IssueStatusFactory(name="Test Status")
        cls.reporter = UserFactory()
        cls.assignee = UserFactory()

    def setUp(self):
        """
        Setup de la prueba, se ejecuta antes de cada test.
        Ideal para limpiar la base de datos o resetear secuencias.
        """
        reset_sequences()
        super().setUp()

    def test_str_representation(self):
        """
        Tests that the __str__ method returns the correct string format.
        """
        issue = IssueFactory(
            status=self.status,
            category=self.category,
            issue_type=self.issue_type,
            administrative_region=self.child_region,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        expected_str = (
            f"{issue.status.name} - {issue.category.name} - {issue.issue_type.name} "
            f"({issue.intake_date.strftime('%Y-%m-%d %H:%M')})"
        )
        self.assertEqual(str(issue), expected_str)

    def test_resolution_days_with_resolution_date(self):
        """
        Tests the resolution_days method when the issue is resolved.
        """
        issue = IssueFactory(
            intake_date=timezone.now() - timedelta(days=5),
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        issue.resolution_date = timezone.now()
        issue.save()
        self.assertEqual(issue.resolution_days(), 5)

    def test_resolution_days_without_resolution_date(self):
        """
        Tests the resolution_days method when the issue is not resolved.
        """
        issue = IssueFactory(
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertIsNone(issue.resolution_days())

    def test_issue_is_created_with_default_contact_medium(self):
        """
        Tests that an Issue is created with the correct default contact_medium.
        """
        issue = IssueFactory(
            contact_medium="channel-alert",
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertEqual(issue.contact_medium, "channel-alert")

    def test_issue_is_created_with_default_intake_date(self):
        """
        Tests that an Issue is created with a default intake_date set to now.
        """
        issue = IssueFactory(
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertIsNotNone(issue.intake_date)

    def test_ongoing_issue_default_is_false(self):
        """
        Tests that the ongoing_issue field defaults to False.
        """
        issue = IssueFactory(
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertFalse(issue.ongoing_issue)

    def test_automatic_tracking_code_generation(self):
        """
        Tests that the tracking_code is automatically populated upon saving.
        """
        issue = IssueFactory(
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        self.assertIsNotNone(issue.tracking_code)

    def test_updated_date_updates_on_save(self):
        """
        Tests that the updated_date field updates on subsequent saves.
        """
        issue = IssueFactory(
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        initial_updated_date = issue.updated_date
        issue.title = "A new title"
        issue.save()
        self.assertGreater(issue.updated_date, initial_updated_date)

    def test_contact_method_is_required_for_non_channel_alert_medium(self):
        """
        Tests that a ValidationError is raised if contact_medium is not 'channel-alert'
        and contact_method is not provided.
        """
        with self.assertRaises(ValidationError):
            IssueFactory(
                contact_medium="facilitator",
                contact_method=None,
                administrative_region=self.child_region,
                category=self.category,
                issue_type=self.issue_type,
                status=self.status,
                reporter=self.reporter,
                assignee=self.assignee,
            )

    def test_contact_information_is_valid_for_email_method(self):
        """
        Tests that a ValidationError is raised if contact_method is 'email' but
        contact_information is not a valid email address.
        """
        with self.assertRaises(ValidationError):
            IssueFactory(
                contact_method="email",
                contact_information="not_an_email",
                administrative_region=self.child_region,
                category=self.category,
                issue_type=self.issue_type,
                status=self.status,
                reporter=self.reporter,
                assignee=self.assignee,
            )

    def test_contact_information_is_valid_for_non_email_method(self):
        """
        Tests that a ValidationError is raised if contact_method is not 'email' but
        contact_information is a valid email address.
        """
        with self.assertRaises(ValidationError):
            IssueFactory(
                contact_method="phone_number",
                contact_information="valid_email@example.com",
                administrative_region=self.child_region,
                category=self.category,
                issue_type=self.issue_type,
                status=self.status,
                reporter=self.reporter,
                assignee=self.assignee,
            )

    def test_valid_issue_saves_correctly(self):
        """
        Tests that an issue with valid data saves without raising errors.
        """
        issue = IssueFactory(
            contact_medium="facilitator",
            contact_method="phone_number",
            contact_information="1234567890",
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
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
        issue = IssueFactory.build(
            contact_medium="facilitator",
            contact_method=None,
            administrative_region=self.child_region,
            category=self.category,
            issue_type=self.issue_type,
            status=self.status,
            reporter=self.reporter,
            assignee=self.assignee,
        )
        with self.assertRaises(ValidationError):
            issue.save()
