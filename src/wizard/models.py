from django.db import models

from grm.constants import (
    COMPLETED_CHOICE,
    NOT_STARTED_CHOICE,
    WIZARD_SECTION_CHOICES,
    WIZARD_STATUS_CHOICES,
)


class WizardSection(models.Model):
    name = models.SlugField(max_length=255, unique=True, choices=WIZARD_SECTION_CHOICES)
    prompt = models.TextField(null=True, blank=True)
    status = models.SlugField(choices=WIZARD_STATUS_CHOICES, default=NOT_STARTED_CHOICE)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wizard Section"
        verbose_name_plural = "Wizard Section"
        ordering = ['id']

    @classmethod
    def wizard_setup_is_completed(cls):
        return not cls.objects.exclude(status=COMPLETED_CHOICE).exists()
