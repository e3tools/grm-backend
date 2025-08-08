import factory
from factory.django import DjangoModelFactory

from authentication.models import User
from issues.models import Issue, IssueStatus, IssueCategory, IssueType, AdministrativeRegion


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


class IssueCategoryFactory(DjangoModelFactory):
    """Factory for creating IssueCategory instances for testing."""

    class Meta:
        model = IssueCategory

    name = factory.Sequence(lambda n: f"Category {n}")


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
    administrative_level = "District"
    parent = None


class IssueFactory(DjangoModelFactory):
    """Factory for creating Issue instances for testing."""

    class Meta:
        model = Issue

    status = factory.SubFactory(IssueStatusFactory)
    category = factory.SubFactory(IssueCategoryFactory)
    issue_type = factory.SubFactory(IssueTypeFactory)
    administrative_region = factory.SubFactory(AdministrativeRegionFactory)
