from django.db import models

from grm.constants import NOT_STARTED_CHOICE, STATUS_CHOICES


class WizardSection(models.Model):
    name = models.CharField(max_length=255, unique=True)
    prompt = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=NOT_STARTED_CHOICE)
    template_name = models.CharField(max_length=255, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wizard Section"
        verbose_name_plural = "Wizard Section"

    @classmethod
    def get_wizard_setup_status(cls):
        return cls.objects.last().status
