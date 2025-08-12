import factory
from factory.django import DjangoModelFactory

from authentication.models import User
from issues.models import AdministrativeRegion, Issue, IssueStatus, IssueType

from .models import (
    AdministrativeLevel,
    IssueCategory,
    IssueDepartment,
    IssueDepartmentAdministrativeLevel,
)


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances for testing."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        password = extracted or 'defaultpass123'
        self.set_password(password)
        self.save()


class IssueStatusFactory(DjangoModelFactory):
    """Factory for creating IssueStatus instances for testing."""

    class Meta:
        model = IssueStatus

    name = factory.Sequence(lambda n: f"Status {n}")
    final_status = False
    initial_status = True
    rejected_status = False
    open_status = True


class AdministrativeLevelFactory(DjangoModelFactory):
    """
    Factory for creating AdministrativeLevel instances.

    Creates administrative levels with unique names for testing purposes.
    Common administrative levels include Country, Region, District, County, etc.
    """

    name = factory.Sequence(lambda n: f"Administrative Level {n}")

    class Meta:
        model = AdministrativeLevel
        django_get_or_create = ('name',)  # Avoid duplicates due to unique constraint


class IssueDepartmentFactory(DjangoModelFactory):
    """
    Factory for creating IssueDepartment instances.

    Creates departments with unique names and optional head assignments.
    The head field can be set to a User instance if needed.
    """

    name = factory.Sequence(lambda n: f"Department {n}")
    head = None  # Can be set to a User instance when needed

    class Meta:
        model = IssueDepartment
        django_get_or_create = ('name',)  # Avoid duplicates due to unique constraint


class IssueDepartmentAdministrativeLevelFactory(DjangoModelFactory):
    """
    Factory for creating IssueDepartmentAdministrativeLevel instances.

    Creates relationships between departments and administrative levels.
    Uses SubFactory to create related instances if not provided.
    """

    department = factory.SubFactory(IssueDepartmentFactory)
    administrative_level = factory.SubFactory(AdministrativeLevelFactory)

    class Meta:
        model = IssueDepartmentAdministrativeLevel
        django_get_or_create = ('department', 'administrative_level')  # Avoid duplicates


class IssueCategoryFactory(DjangoModelFactory):
    """
    Factory for creating IssueCategory instances.

    Creates issue categories with all required department assignments.
    Uses SubFactory to create the necessary department-administrative level relationships.
    """

    name = factory.Sequence(lambda n: f"Issue Category {n}")
    abbreviation = factory.LazyAttribute(lambda obj: obj.name[:3].upper())

    # Department assignments - using SubFactory to create relationships
    assigned_department = factory.SubFactory(IssueDepartmentAdministrativeLevelFactory)
    assigned_appeal_department = factory.SubFactory(IssueDepartmentAdministrativeLevelFactory)
    assigned_escalation_department = factory.SubFactory(IssueDepartmentAdministrativeLevelFactory)

    # Optional fields with sensible defaults
    confidentiality_level = factory.fuzzy.FuzzyChoice(['Public', 'Internal', 'Confidential', 'Restricted', 'Secret'])
    redirection_protocol = factory.fuzzy.FuzzyInteger(0, 5)

    class Meta:
        model = IssueCategory
        django_get_or_create = ('name',)  # Avoid duplicates due to unique constraint


class IssueTypeFactory(DjangoModelFactory):
    """Factory for creating IssueType instances for testing."""

    class Meta:
        model = IssueType

    name = factory.Sequence(lambda n: f"Type {n}")


class AdministrativeRegionFactory(DjangoModelFactory):
    """Factory for creating AdministrativeRegion instances for testing."""

    class Meta:
        model = AdministrativeRegion

    name = factory.Sequence(lambda n: f"Region {n}")
    latitude = factory.Faker('latitude')
    longitude = factory.Faker('longitude')
    administrative_level = factory.SubFactory(AdministrativeLevelFactory)
    parent = None


class IssueFactory(DjangoModelFactory):
    """Factory for creating Issue instances for testing."""

    class Meta:
        model = Issue

    status = factory.SubFactory(IssueStatusFactory)
    category = factory.SubFactory(IssueCategoryFactory)
    issue_type = factory.SubFactory(IssueTypeFactory)
    administrative_region = factory.SubFactory(AdministrativeRegionFactory)
