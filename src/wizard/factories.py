import factory
from factory.django import DjangoModelFactory
from faker import Faker

from wizard.models import WizardSection

fake = Faker()


class WizardSectionFactory(DjangoModelFactory):
    """Factory for creating WizardSectionFactory instances for testing."""

    class Meta:
        model = WizardSection

    name = factory.Sequence(lambda n: f"section_{n}")
