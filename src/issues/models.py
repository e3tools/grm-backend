from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.utils import timezone
from django.utils.timezone import now
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


class Component(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(
        null=False,
        blank=False,
        default=None
    )

    def __str__(self):
        return self.name


class SubComponent(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


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


class IssueSubType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', db_index=True
    )

    class Meta:
        verbose_name = _("Issue Subtype")
        verbose_name_plural = _("Issue Subtypes")
        ordering = ['name']

    def __str__(self):
        return self.name


class CitizenAgeGroup(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class CitizenGroup(models.Model):
    CITIZEN_GROUP_TYPE = (
        ('citizen_group', _('citizen_group')),
        ('citizen_group_2', _('citizen_group_2')),
    )
    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=50, blank=True, choices=CITIZEN_GROUP_TYPE)

    def __str__(self):
        return self.name


class Citizen(models.Model):
    CITIZEN_TYPE = (
        ('organization_behalf_someone', _('organization_behalf_someone')),
        ('on_behalf_of_someone', _('on_behalf_of_someone')),
        ('keep_name_confidential', _('keep_name_confidential'))
    )

    name = models.CharField(max_length=255)
    age_group = models.ForeignKey(CitizenAgeGroup, blank=True, on_delete=models.CASCADE,
                                  related_name="age_group_citizen")
    type = models.CharField(max_length=50, blank=True, choices=CITIZEN_TYPE)
    group = models.ForeignKey(CitizenGroup, blank=True, on_delete=models.CASCADE, related_name="group_citizen")
    group_2 = models.ForeignKey(CitizenGroup, blank=True, on_delete=models.CASCADE, related_name="group2_citizen")


class Issue(models.Model):
    CONTACT_MEDIUM = (
        ('channel-alert', _('channel-alert')),
        ('facilitator', _('facilitator')),
        ('anonymous', _('anonymous'))
    )
    CONTACT_METHOD = (
        ('email', _('email')),
        ('phone_number', _('phone_number')),
        ('whatsapp', _('whatsapp'))
    )

    administrative_region = models.ForeignKey(AdministrativeRegion, on_delete=models.CASCADE, related_name='issues')
    assignee = models.ForeignKey('authentication.User', on_delete=models.CASCADE, related_name='assigned_issues')
    category = models.ForeignKey(IssueCategory, on_delete=models.CASCADE, related_name='issues')
    citizen = models.ForeignKey(Citizen, blank=True, on_delete=models.CASCADE, related_name="citizen_issues")
    contact_information = models.CharField(max_length=255, blank=True,
                                           help_text="The contact phone, email, whatsapp or other method data")
    contact_medium = models.CharField(max_length=50, blank=True, choices=CONTACT_MEDIUM, default='channel-alert')
    contact_method = models.CharField(max_length=255, choices=CONTACT_METHOD, default=None, null=True)
    component = models.ForeignKey(
        Component,
        on_delete=models.CASCADE,
        related_name='issues',
        null=True
    )
    created_date = models.DateTimeField(blank=True, editable=False, null=True, auto_now_add=now(),
                                        help_text="When was the issue created in DB")
    description = models.TextField(
        null=False,
        blank=False,
        default=None
    )
    intake_date = models.DateTimeField(default=timezone.now, db_index=True, help_text="When was the issue was reported")
    issue_date = models.DateTimeField(blank=True, editable=False, null=True, help_text="When was the issue happened")
    issue_location = models.ForeignKey(
        AdministrativeRegion,
        on_delete=models.CASCADE,
        related_name='located_issues',
        null=True,
        blank=True,
        help_text="The specific administrative location where the issue occurred."
    )
    issue_type = models.ForeignKey(IssueType, on_delete=models.CASCADE, related_name='issues')
    issue_sub_type = models.ForeignKey(
        IssueSubType,
        on_delete=models.CASCADE,
        related_name='issues',
        null=True,
    )
    location_description = models.TextField(blank=True, help_text="A textual description of the issue's location.")
    ongoing_issue = models.BooleanField(default=False)
    reporter = models.ForeignKey('authentication.User', on_delete=models.CASCADE, related_name='reporter_issues')
    resolution_date = models.DateTimeField(blank=True, editable=False, null=True,
                                           help_text="When was the issue was resolved")
    status = models.ForeignKey(IssueStatus, on_delete=models.CASCADE, related_name='issues')
    sub_component = models.ForeignKey(
        SubComponent,
        on_delete=models.CASCADE,
        related_name='issues',
        null=True
    )
    title = models.CharField(max_length=255)
    tracking_code = models.CharField(max_length=255)
    updated_date = models.DateTimeField(blank=True, editable=False, null=True, auto_now=now())

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

    def save(self, *args, **kwargs):
        self._validate_contact_method_based_on_contact_medium()
        return super().save(*args, **kwargs)

    def _validate_contact_method_based_on_contact_medium(self):
        if self.contact_medium != 'channel-alert' and self.contact_method is None:
            raise ValidationError(
                _("You must define the contact method is your contact medium is not channel alert"),
            )

    def _validate_contact_information_based_on_contact_method(self):
        if self.contact_method == 'email' and not validate_email(self.contact_information):
            raise ValidationError(
                _("If email contact method is selected provide a valid email"),
            )
        if self.contact_method != 'email' and validate_email(self.contact_information):
            raise ValidationError(
                _("If phone or whatsapp contact method is selected provide a valid phone number"),
            )

    def resolution_days(self):
        if self.resolution_date is not None:
            return abs((self.intake_date - self.resolution_date).days)
        return None
