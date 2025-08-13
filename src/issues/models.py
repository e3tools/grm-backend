from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AdministrativeLevel(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = _("Administrative Level")
        verbose_name_plural = _("Administrative Levels")
        ordering = ['name']

    def __str__(self):
        return self.name


class AdministrativeRegion(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    administrative_level = models.ForeignKey(
        AdministrativeLevel, on_delete=models.CASCADE, related_name='regions', db_index=True
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', db_index=True
    )

    class Meta:
        verbose_name = _("Administrative Region")
        verbose_name_plural = _("Administrative Regions")
        ordering = ['name']
        indexes = [
            models.Index(fields=['parent', 'administrative_level']),
        ]

    def save(self, *args, **kwargs):
        # Validation to ensure only one AdministrativeRegion with no parent exists
        if self.parent is None:
            qs = AdministrativeRegion.objects.filter(parent__isnull=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError("Only one AdministrativeRegion can have no parent.")
        super().save(*args, **kwargs)

    def __str__(self):
        if self.parent:
            return f"{self.name} ({self.administrative_level.name}) - {self.parent.name}"
        return f"{self.name} ({self.administrative_level.name})"

    def get_full_hierarchy(self):
        """
        Returns the full hierarchical path of the administrative region.
        """
        hierarchy = [self.name]
        parent = self.parent
        while parent:
            hierarchy.append(parent.name)
            parent = parent.parent
        return " > ".join(reversed(hierarchy))

    def get_all_descendant_ids(self):
        descendant_ids = [self.id]
        children = list(self.children.all())
        for child in children:
            descendant_ids.extend(child.get_all_descendant_ids())
        return descendant_ids


class IssueStatus(models.Model):
    name = models.CharField(max_length=255, unique=True)
    final_status = models.BooleanField(default=False)
    initial_status = models.BooleanField(default=False)
    rejected_status = models.BooleanField(default=False)
    open_status = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Issue Status")
        verbose_name_plural = _("Issue Status")
        ordering = ['name']

    def __str__(self):
        return self.name


class IssueDepartment(models.Model):
    name = models.CharField(max_length=255, unique=True)
    head = models.ForeignKey('authentication.User', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = _("Issue Department")
        verbose_name_plural = _("Issue Departments")
        ordering = ['name']

    def __str__(self):
        return self.name


class IssueDepartmentAdministrativeLevel(models.Model):
    department = models.ForeignKey(IssueDepartment, on_delete=models.CASCADE)
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)

    class Meta:
        unique_together = ['department', 'administrative_level']

    def __str__(self):
        return f"{self.department.name} - {self.administrative_level.name}"


class IssueCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    abbreviation = models.CharField(max_length=255, unique=False, blank=True, null=True)
    assigned_department = models.ForeignKey(
        IssueDepartmentAdministrativeLevel, on_delete=models.CASCADE, related_name='assigned_categories'
    )
    assigned_appeal_department = models.ForeignKey(
        IssueDepartmentAdministrativeLevel, on_delete=models.CASCADE, related_name='assigned_appeal_categories'
    )
    assigned_escalation_department = models.ForeignKey(
        IssueDepartmentAdministrativeLevel, on_delete=models.CASCADE, related_name='assigned_escalation_categories'
    )
    confidentiality_level = models.CharField(max_length=255, null=True, blank=True)
    redirection_protocol = models.IntegerField(default=0)

    class Meta:
        verbose_name = _("Issue Category")
        verbose_name_plural = _("Issue Categories")
        ordering = ['name']

    def __str__(self):
        return self.name


class IssueType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = _("Issue Type")
        verbose_name_plural = _("Issue Types")
        ordering = ['name']

    def __str__(self):
        return self.name


class Issue(models.Model):
    intake_date = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.ForeignKey(IssueStatus, on_delete=models.CASCADE, related_name='issues')
    category = models.ForeignKey(IssueCategory, on_delete=models.CASCADE, related_name='issues')
    issue_type = models.ForeignKey(IssueType, on_delete=models.CASCADE, related_name='issues')
    administrative_region = models.ForeignKey(AdministrativeRegion, on_delete=models.CASCADE, related_name='issues')

    class Meta:
        verbose_name = _("Issue")
        verbose_name_plural = _("Issues")
        ordering = ['-intake_date']
        indexes = [
            models.Index(fields=['intake_date', 'administrative_region']),
            models.Index(fields=['administrative_region', 'status']),
            models.Index(fields=['administrative_region', 'category']),
            models.Index(fields=['administrative_region', 'issue_type']),
        ]

    def __str__(self):
        return (
            f"{self.status.name} - {self.category.name} - {self.issue_type.name} "
            f"({self.intake_date.strftime('%Y-%m-%d %H:%M')})"
        )
