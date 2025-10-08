from django.db import models
from django.utils.translation import gettext_lazy as _


class Project(models.Model):
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    description = models.TextField(null=True, blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")
