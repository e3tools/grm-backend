from django.db import models

from wizard.constants import (
    COMPLETED_CHOICE,
    NOT_STARTED_CHOICE,
    WIZARD_SECTION_CHOICES,
    WIZARD_STATUS_CHOICES,
)


class WizardSection(models.Model):
    step = models.PositiveIntegerField(unique=True)
    name = models.SlugField(max_length=255, unique=True, choices=WIZARD_SECTION_CHOICES)
    prompt = models.TextField(null=True, blank=True)
    status = models.SlugField(choices=WIZARD_STATUS_CHOICES, default=NOT_STARTED_CHOICE)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wizard Section"
        verbose_name_plural = "Wizard Sections"
        ordering = ['step']

    @classmethod
    def wizard_setup_is_completed(cls):
        return not cls.objects.exclude(status=COMPLETED_CHOICE).exists()

    @classmethod
    def reorder_steps(cls):
        """
        Reorder all steps sequentially starting from 1.
        Useful after deletions to maintain consecutive numbering.

        Example:
            WizardSection.reorder_steps()
        """
        sections = cls.objects.all().order_by('step')
        for index, section in enumerate(sections, start=1):
            if section.step != index:
                section.step = index
                section.save(update_fields=['step'])
