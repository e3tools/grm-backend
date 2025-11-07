import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from authentication.models import Citizen, Facilitator, User


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances for testing."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    grm_owner = False

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        password = extracted or 'defaultpass123'
        self.set_password(password)
        self.save()


class FacilitatorFactory(DjangoModelFactory):
    """Factory for creating Facilitator instances."""

    class Meta:
        model = Facilitator

    user = factory.SubFactory(UserFactory)
    administrative_region = factory.SubFactory("issues.factories.AdministrativeRegionFactory")
    unique_region = True
    village_secretary = None


class CitizenFactory(factory.django.DjangoModelFactory):
    """
    Factory for authentication.Citizen model.

    Automatically creates:
      - A related authentication.User
      - A related issues.Citizen (if not provided)
    """

    class Meta:
        model = Citizen

    user = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def citizen(self):
        """
        Lazy create of related issues.Citizen using dynamic import
        to avoid circular import between apps.
        """
        from issues.factories import CitizenFactory as IssuesCitizenFactory

        return IssuesCitizenFactory(name=self.user.name)

    created_date = factory.LazyFunction(timezone.now)
    updated_date = factory.LazyFunction(timezone.now)
