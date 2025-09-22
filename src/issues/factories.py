import random

import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from factory import fuzzy
from factory.django import DjangoModelFactory
from faker import Faker

from authentication.factories import UserFactory
from issues.models import (
    AdministrativeLevel,
    AdministrativeRegion,
    Citizen,
    CitizenAgeGroup,
    CitizenGroup,
    Comment,
    Component,
    Issue,
    IssueAttachment,
    IssueCategory,
    IssueDepartment,
    IssueDepartmentAdministrativeLevel,
    IssueStatus,
    IssueSubType,
    IssueType,
    SubComponent,
    SubProjectGroup,
)

fake = Faker()


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


class IssueSubTypeFactory(DjangoModelFactory):
    """Factory for creating IssueSubTypeFactory instances for testing."""

    class Meta:
        model = IssueSubType

    name = factory.Sequence(lambda n: f"SubType {n}")
    parent = None


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
    parent = factory.SubFactory(IssueSubTypeFactory)

    # Optional fields with sensible defaults
    confidentiality_level = fuzzy.FuzzyChoice(['Public', 'Internal', 'Confidential', 'Restricted', 'Secret'])
    redirection_protocol = fuzzy.FuzzyInteger(0, 5)

    class Meta:
        model = IssueCategory
        django_get_or_create = ('name',)  # Avoid duplicates due to unique constraint


class IssueTypeFactory(DjangoModelFactory):
    """Factory for creating IssueType instances for testing."""

    class Meta:
        model = IssueType

    name = factory.Sequence(lambda n: f"Type {n}")


class ComponentFactory(DjangoModelFactory):
    """Factory for creating Component instances for testing."""

    class Meta:
        model = Component


class SubComponentFactory(DjangoModelFactory):
    """Factory for creating SubComponent instances for testing."""

    class Meta:
        model = SubComponent

    parent = factory.SubFactory(ComponentFactory)


class AdministrativeRegionFactory(DjangoModelFactory):
    """Factory for creating AdministrativeRegion instances for testing."""

    class Meta:
        model = AdministrativeRegion

    name = factory.Sequence(lambda n: f"Region {n}")
    latitude = factory.Faker('latitude')
    longitude = factory.Faker('longitude')
    administrative_level = factory.SubFactory(AdministrativeLevelFactory)
    parent = None


class SubProjectGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SubProjectGroup

    name = factory.Sequence(lambda n: f"{n}")


class CitizenAgeGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CitizenAgeGroup

    name = factory.Sequence(lambda n: f"{n}")


class CitizenGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CitizenGroup

    name = factory.Sequence(lambda n: f"{n}")
    type = factory.Sequence(lambda n: f"{n}")


class CitizenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Citizen

    age_group = factory.SubFactory(CitizenAgeGroupFactory)
    group = factory.SubFactory(CitizenGroupFactory)
    group_2 = factory.SubFactory(CitizenGroupFactory)


class IssueFactory(DjangoModelFactory):
    """Factory for creating Issue instances for testing."""

    class Meta:
        model = Issue

    tracking_code = factory.Sequence(lambda n: f"TRK-{n + 1:05d}")
    description = factory.LazyFunction(lambda: fake.paragraph(nb_sentences=3))
    intake_date = factory.LazyFunction(timezone.now)
    status = factory.SubFactory(IssueStatusFactory)
    category = factory.SubFactory(IssueCategoryFactory)
    issue_type = factory.SubFactory(IssueTypeFactory)
    administrative_region = factory.SubFactory(AdministrativeRegionFactory)
    reporter = factory.SubFactory(UserFactory)
    assignee = factory.SubFactory(UserFactory)
    rating = factory.LazyFunction(lambda: random.randint(1, 5))


class CommentFactory(DjangoModelFactory):
    """Factory for creating Comment instances for testing."""

    class Meta:
        model = Comment

    comment = factory.Faker("sentence", nb_words=10)
    user = factory.SubFactory(UserFactory)
    issue = factory.SubFactory(IssueFactory)
    due_date = factory.LazyFunction(timezone.now)


class IssueAttachmentFactory(DjangoModelFactory):
    """Factory for creating Attachment instances for testing."""

    class Meta:
        model = IssueAttachment

    created_date = factory.LazyFunction(timezone.now)
    issue = factory.SubFactory(IssueFactory)
    uploaded_by = factory.SubFactory(UserFactory)
    updated_date = factory.LazyFunction(timezone.now)

    @factory.lazy_attribute
    def file(self):
        return SimpleUploadedFile(name='test.txt', content=b'Test content', content_type='text/plain')
