import os

import cryptocode
import shortuuid as uuid
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models, transaction
from django.db.models import Count
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from authentication.models import Cdata, Facilitator, GovernmentWorker, Pdata, User
from dashboard.constants import STATUS_AT_RISK, STATUS_CRITICAL, STATUS_GOOD, STATUS_NA
from grm.constants import (
    ALERT_CHOICE,
    ALERT_CHOICES,
    ANONYMOUS_CHOICE,
    CITIZEN_TYPE_CHOICES,
    CONFIDENTIALITY_LEVEL_CHOICES,
    CONTACT_CHOICES,
    CONTACT_MEDIUM_ERROR_MESSAGE,
    FEWER_ISSUES_CHOICE,
    GENDER_CHOICES,
    LOW_CHOICE,
    MEDIUM_CHOICES,
    REDIRECTION_PROTOCOL_CHOICES,
)
from grm.utils import filesizeformat_en, get_choices
from wizard.constants import CITIZEN_GROUP_CHOICES


class AdministrativeLevel(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Administrative Level")
        verbose_name_plural = _("Administrative Levels")
        ordering = ['id']

    def __str__(self):
        return self.name

    @classmethod
    def get_regions_summary(cls):
        """Returns a summary of regions by administrative level."""
        return cls.objects.annotate(region_count=Count("regions")).order_by("id").values("id", "name", "region_count")


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
    hierarchical_name = models.TextField(default='', db_index=True, verbose_name=_('Hierarchical Name'))
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

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

        # Update hierarchical_name before saving
        update_hierarchy = kwargs.pop('update_hierarchy', True)
        if update_hierarchy:
            self.hierarchical_name = self._build_hierarchical_name()

        super().save(*args, **kwargs)

        # Update children's hierarchy if this region's name changed
        if update_hierarchy and self.pk:
            self._update_children_hierarchy()

    def __str__(self):
        return self.hierarchical_name

    def _build_hierarchical_name(self):
        """
        Builds the hierarchical name of the administrative region.
        Order: current region -> parent -> grandparent -> root
        """
        hierarchy = [self.name]
        parent = self.parent
        while parent:
            hierarchy.append(parent.name)
            parent = parent.parent
        return ", ".join(hierarchy)

    def _update_children_hierarchy(self):
        """
        Updates hierarchical_name for all descendants using a single query.
        """
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH RECURSIVE hierarchy_update AS (
                    -- Base case: direct children of the current region
                    SELECT ar.id,
                           ar.name,
                           ar.parent_id,
                           ar.name || ', ' || %s AS new_hierarchy
                    FROM issues_administrativeregion ar
                    WHERE ar.parent_id = %s

                    UNION ALL

                    -- Recursive case: children of children
                    SELECT ar.id,
                           ar.name,
                           ar.parent_id,
                           ar.name || ', ' || hu.new_hierarchy AS new_hierarchy
                    FROM issues_administrativeregion ar
                             INNER JOIN hierarchy_update hu ON ar.parent_id = hu.id)
                UPDATE issues_administrativeregion
                SET hierarchical_name = hierarchy_update.new_hierarchy FROM hierarchy_update
                WHERE issues_administrativeregion.id = hierarchy_update.id
                """,
                [self.hierarchical_name, self.id],
            )

    def get_full_hierarchy_ids(self):
        hierarchy_ids = [self.id]
        parent = self.parent
        while parent:
            hierarchy_ids.append(parent.id)
            parent = parent.parent
        return hierarchy_ids[::-1]

    def get_descendant_ids(self, include_self=True):
        """
        Returns the IDs of all descendants in this region
        using a recursive CTE in PostgreSQL.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH RECURSIVE descendants AS (
                    SELECT id, parent_id
                    FROM {table}
                    WHERE id = %s
                    UNION ALL
                    SELECT ar.id, ar.parent_id
                    FROM {table} ar
                    INNER JOIN descendants d ON ar.parent_id = d.id
                )
                SELECT id FROM descendants
                """.format(
                    table=self._meta.db_table
                ),
                [self.id],
            )
            ids = [row[0] for row in cursor.fetchall()]

        if not include_self:
            ids.remove(self.id)

        return ids

    def belongs_to_region(self, parent):
        if parent == self:
            belongs = True
        else:
            belongs = self.id in parent.get_descendant_ids()
        return belongs

    def get_base_region_id(self):
        base_region_id = self.id
        parent = self.parent
        while parent and parent.parent:
            base_region_id = parent.id
            parent = parent.parent
        return base_region_id

    @classmethod
    def get_first_level_choices(cls, empty_choice=True):
        query_result = cls.objects.filter(parent__parent__isnull=True).exclude(parent__isnull=True)
        choices = list()
        for item in query_result:
            choices.append((item.id, item.name))
        if empty_choice:
            choices = [("", "")] + choices
        return choices

    @classmethod
    def get_first_child_level_name(cls):
        first_child = cls.objects.filter(parent__parent=None).first()
        if first_child:
            return first_child.administrative_level.name.title()


class Component(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=False, blank=False)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Component")
        verbose_name_plural = _("Components")

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)


class SubComponent(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=False, blank=False)
    parent = models.ForeignKey(Component, on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Subcomponent")
        verbose_name_plural = _("Subcomponents")
        unique_together = ['name', 'parent']

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True, parent=None):
        choices = cls.objects.all() if not parent else cls.objects.filter(parent=parent)
        return get_choices(choices, empty_choice)


class SubProjectGroup(models.Model):
    name = models.CharField(max_length=100)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Subproject Group")
        verbose_name_plural = _("Subproject Groups")

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)


class IssueStatus(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name=_('Name'))
    threshold_days = models.PositiveIntegerField(
        default=1, help_text=_("Threshold in days for performance evaluation"), verbose_name=_('Threshold days')
    )
    threshold_days_to_escalate = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=_("Threshold in days to escalate an issue"),
        verbose_name=_('Threshold days to escalate'),
    )
    final_status = models.BooleanField(default=False)
    initial_status = models.BooleanField(default=False)
    rejected_status = models.BooleanField(default=False)
    open_status = models.BooleanField(default=False)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Issue Status")
        verbose_name_plural = _("Issue Status")
        ordering = ['id']
        constraints = [
            models.CheckConstraint(
                check=models.Q(threshold_days__gt=0),
                name="%(app_label)s_%(class)s_threshold_days_gt_0",
                violation_error_message=_("Threshold must be greater than zero."),
            )
        ]

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)

    def performance_for_status(self, avg_days):
        """
        Determine the performance dictionary for this IssueStatus given an average time in days.

        Returns a dict with keys:
          - badge_text: human label ("Critical", "At Risk", "Good", "N/A")
          - badge_class, icon_class: visual metadata (from dashboard.constants)

        Acceptance criteria:
          - Critical: avg_days > threshold * 1.5
          - At Risk: avg_days > threshold * 1.2
          - Good: avg_days <= threshold * 1.2
        """
        if avg_days is None:
            return STATUS_NA
        try:
            avg = float(avg_days)
        except Exception:
            return STATUS_NA

        threshold = self.threshold_days or 1.0
        # Compare average days to threshold
        if avg > threshold * 1.5:
            return STATUS_CRITICAL
        if avg > threshold * 1.2:
            return STATUS_AT_RISK
        return STATUS_GOOD


class IssueDepartment(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Name"))
    head = models.ForeignKey('authentication.User', null=True, blank=True, on_delete=models.SET_NULL)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Issue Department")
        verbose_name_plural = _("Issue Departments")
        ordering = ['name']

    def __str__(self):
        return self.name


class IssueDepartmentAdministrativeLevel(models.Model):
    department = models.ForeignKey(IssueDepartment, on_delete=models.CASCADE)
    administrative_level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        unique_together = ['department', 'administrative_level']

    def __str__(self):
        return f"{self.department.name} - {self.administrative_level.name}"


class IssueType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Issue Type")
        verbose_name_plural = _("Issue Types")
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)


class IssueSubType(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(IssueType, on_delete=models.CASCADE, related_name='children', db_index=True)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Issue Subtype")
        verbose_name_plural = _("Issue Subtypes")
        ordering = ['name']
        unique_together = ['name', 'parent']

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True, parent=None):
        choices = cls.objects.all() if not parent else cls.objects.filter(parent=parent)
        return get_choices(choices, empty_choice)


class IssueCategory(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Name"))
    abbreviation = models.CharField(max_length=255, unique=False, blank=True, null=True, verbose_name=_("Abbreviation"))
    assigned_department = models.ForeignKey(
        IssueDepartmentAdministrativeLevel, on_delete=models.CASCADE, related_name='assigned_categories'
    )
    assigned_appeal_department = models.ForeignKey(
        IssueDepartmentAdministrativeLevel, on_delete=models.CASCADE, related_name='assigned_appeal_categories'
    )

    # TODO: Remove this field
    assigned_escalation_department = models.ForeignKey(
        IssueDepartmentAdministrativeLevel, on_delete=models.CASCADE, related_name='assigned_escalation_categories'
    )

    parent = models.ForeignKey(IssueSubType, blank=True, null=True, on_delete=models.CASCADE, related_name='categories')
    confidentiality_level = models.SlugField(
        default=LOW_CHOICE, choices=CONFIDENTIALITY_LEVEL_CHOICES, verbose_name=_("Confidentiality level")
    )
    redirection_protocol = models.SlugField(
        default=FEWER_ISSUES_CHOICE, choices=REDIRECTION_PROTOCOL_CHOICES, verbose_name=_("Redirection protocol")
    )
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Issue Category")
        verbose_name_plural = _("Issue Categories")
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True, parent=None):
        choices = cls.objects.all() if not parent else cls.objects.filter(parent=parent)
        return get_choices(choices, empty_choice)


class CitizenAgeGroup(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Citizen Age Group")
        verbose_name_plural = _("Citizen Age Groups")

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)


class CitizenGroup(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name=_('Name'))
    type = models.SlugField(max_length=50, blank=True, choices=CITIZEN_GROUP_CHOICES, verbose_name=_('Type'))
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Citizen Group")
        verbose_name_plural = _("Citizen Groups")

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)


class Citizen(models.Model):
    name = models.CharField(max_length=255)
    age_group = models.ForeignKey(
        CitizenAgeGroup, null=True, blank=True, on_delete=models.CASCADE, related_name="age_group_citizen"
    )
    type = models.SlugField(null=True, blank=True, choices=CITIZEN_TYPE_CHOICES)
    gender = models.SlugField(null=True, blank=True, choices=GENDER_CHOICES)
    group = models.ForeignKey(
        CitizenGroup, null=True, blank=True, on_delete=models.CASCADE, related_name="group_citizen"
    )
    group_2 = models.ForeignKey(
        CitizenGroup, null=True, blank=True, on_delete=models.CASCADE, related_name="group2_citizen"
    )
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Citizen")
        verbose_name_plural = _("Citizens")

    def __str__(self):
        return f'{self.id} {self.name}'


class IssueStatusChange(models.Model):
    """
    Historical record of when an Issue enters and exits an IssueStatus.

    Each time an Issue changes status:
      - a new IssueStatusChange row is created with entered_at
      - the previous open IssueStatusChange for that issue (if any) is closed by setting exited_at

    Note: We intentionally do NOT create IssueStatusChange rows for statuses that are
    terminal (final_status=True) or rejected (rejected_status=True) to avoid storing
    rows that are not needed for bottleneck calculations.
    """

    issue = models.ForeignKey('Issue', on_delete=models.CASCADE, related_name='status_changes')
    status = models.ForeignKey('IssueStatus', on_delete=models.PROTECT, related_name='status_changes')
    entered_at = models.DateTimeField(default=now, db_index=True)
    exited_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = _("Issue Status Change")
        verbose_name_plural = _("Issue Status Changes")
        ordering = ['-entered_at']
        indexes = [
            models.Index(fields=['issue', 'status', 'entered_at']),
            models.Index(fields=['status', 'entered_at']),
        ]

    def __str__(self):
        return f"Issue {self.issue_id} - {self.status.name} @ {self.entered_at.isoformat()}"

    @property
    def duration_seconds(self):
        end = self.exited_at or now()
        return (end - self.entered_at).total_seconds()

    @property
    def duration_days(self):
        return self.duration_seconds / 86400.0


class Issue(models.Model):
    external_id = models.CharField(
        max_length=255, verbose_name="couchDB document _id", default=None, null=True, blank=True
    )
    administrative_region = models.ForeignKey(
        AdministrativeRegion,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name='issues',
        help_text="The specific administrative location where the issue occurred.",
    )
    assignee = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE, related_name='assigned_issues')
    category = models.ForeignKey(IssueCategory, blank=True, null=True, on_delete=models.CASCADE, related_name='issues')
    citizen = models.ForeignKey(Citizen, blank=True, null=True, on_delete=models.CASCADE, related_name="citizen_issues")
    contact_information = models.CharField(
        max_length=255, blank=True, null=True, help_text="The contact phone, email, whatsapp or other method data"
    )
    contact_medium = models.SlugField(blank=True, choices=MEDIUM_CHOICES, default=ANONYMOUS_CHOICE)
    contact_method = models.SlugField(choices=CONTACT_CHOICES, default=None, null=True, blank=True)
    component = models.ForeignKey(Component, on_delete=models.CASCADE, related_name='issues', null=True, blank=True)
    created_date = models.DateTimeField(
        blank=True, editable=False, null=True, default=now, help_text="When was the issue created in DB"
    )
    description = models.TextField(null=True, blank=True, default=None)
    research_result = models.TextField(null=True, blank=True, default="")
    reject_reason = models.TextField(null=True, blank=True, default="")
    intake_date = models.DateTimeField(
        null=True, blank=True, default=now, db_index=True, help_text="When was the issue was reported"
    )
    issue_date = models.DateTimeField(blank=True, editable=False, null=True, help_text="When was the issue happened")
    issue_type = models.ForeignKey(IssueType, on_delete=models.CASCADE, related_name='issues', null=True, blank=True)
    issue_sub_type = models.ForeignKey(
        IssueSubType, on_delete=models.CASCADE, related_name='issues', null=True, blank=True
    )
    location_description = models.TextField(
        null=True, blank=True, help_text="A textual description of the issue's location."
    )
    ongoing_issue = models.BooleanField(default=False)
    reporter = models.ForeignKey('authentication.User', on_delete=models.CASCADE, related_name='reporter_issues')
    resolution_date = models.DateTimeField(
        blank=True, editable=False, null=True, help_text="When was the issue was resolved"
    )
    status = models.ForeignKey(IssueStatus, null=True, blank=True, on_delete=models.CASCADE, related_name='issues')
    sub_component = models.ForeignKey(
        SubComponent, on_delete=models.CASCADE, related_name='issues', null=True, blank=True
    )
    subproject_group = models.ForeignKey(
        SubProjectGroup, on_delete=models.CASCADE, related_name='issues', null=True, blank=True
    )
    tracking_code = models.CharField(max_length=255)
    internal_code = models.CharField(max_length=255, null=True, blank=True)
    updated_date = models.DateTimeField(
        blank=True, editable=False, null=True, auto_now=now(), verbose_name=_('Updated at')
    )
    confirmed = models.BooleanField(default=False)
    escalated_date = models.DateTimeField(blank=True, editable=False, null=True)
    escalate_flag = models.BooleanField(default=False)
    alert_message_status = models.SlugField(blank=True, default="", choices=ALERT_CHOICES)
    reject_flag = models.BooleanField(default=False)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=0)
    escalation_reason = models.TextField(null=True, blank=True)
    appeal_status = models.BooleanField(default=False)
    vectorized = models.BooleanField(default=False)

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
        return f"{self.id}"

    def save(self, *args, **kwargs):
        """
        Override save to:
          1. Apply contact-method validation.
          2. Maintain IssueStatusChange history.

        Behavior:
          - On create: if the issue has a status, create an initial IssueStatusChange row.
          - On update: if status changed, close the previous open IssueStatusChange (set exited_at)
            and create a new IssueStatusChange for the new status.
        """
        # Apply contact-method validation (existing behavior)
        self._validate_contact_method_based_on_contact_medium()

        # Detect create vs update and capture previous status_id
        is_create = self._state.adding
        old_status_id = None
        if not is_create:
            try:
                old = self.__class__.objects.only('status_id').get(pk=self.pk)
                old_status_id = getattr(old, 'status_id', None)
            except self.__class__.DoesNotExist:
                old_status_id = None

        # Save the Issue first so we have a PK for related IssueStatusChange rows
        with transaction.atomic():
            super().save(*args, **kwargs)

            new_status_id = getattr(self, 'status_id', None)

            # Helper: check whether a status id corresponds to a terminal/rejected status
            def _is_terminal_or_rejected(status_id):
                if not status_id:
                    return False
                try:
                    st = IssueStatus.objects.only('final_status', 'rejected_status').get(pk=status_id)
                    return bool(st.final_status or st.rejected_status)
                except IssueStatus.DoesNotExist:
                    return False

            # Creation: if initial status is non-terminal create a change row,
            # otherwise persist resolution_date immediately (no IssueStatusChange for terminal statuses)
            if is_create and new_status_id:
                if _is_terminal_or_rejected(new_status_id):
                    # Persist resolution_date without calling save() again to avoid recursion
                    self.__class__.objects.filter(pk=self.pk).update(resolution_date=now())
                else:
                    IssueStatusChange.objects.create(issue=self, status_id=new_status_id, entered_at=now())
                return

            # If status didn't change, nothing else to do
            if old_status_id == new_status_id:
                return

            # Close previous open change for this issue (if any)
            prev_open = (
                IssueStatusChange.objects.filter(issue=self, exited_at__isnull=True).order_by('-entered_at').first()
            )
            if prev_open:
                prev_open.exited_at = now()
                prev_open.save(update_fields=['exited_at'])

            # If new status is terminal/rejected: persist resolution_date (DB update) and do NOT create a new change row
            if new_status_id and _is_terminal_or_rejected(new_status_id):
                # Use update to avoid triggering save() again and to ensure the field is persisted
                self.__class__.objects.filter(pk=self.pk).update(resolution_date=now())
            # Otherwise create a new IssueStatusChange row for the new status
            elif new_status_id:
                IssueStatusChange.objects.create(issue=self, status_id=new_status_id, entered_at=now())

    def _validate_contact_method_based_on_contact_medium(self):
        if self.contact_medium == ALERT_CHOICE and not self.contact_method:
            raise ValidationError(CONTACT_MEDIUM_ERROR_MESSAGE)

    def resolution_days(self):
        if self.resolution_date is not None:
            return abs((self.resolution_date - self.intake_date).days)
        return None

    def is_piu_staff(self, user):
        """
        Determine if a Case Manager (GovernmentWorker) is PIU staff for this issue.

        PIU staff criteria:
        1) User is the assignee of the issue; OR
        2) User is HEAD of their own department AND
           - Issue's category is assigned to that department AND
           - Issue's administrative_region is equal to OR a descendant of the worker's region.
        """
        try:
            # Must be a GovernmentWorker (Case Manager)
            if not hasattr(user, "governmentworker"):
                return False

            worker = user.governmentworker

            # 1) Direct assignee
            if self.assignee_id and user.id == self.assignee_id:
                return True

            # 2) Head of department AND (category assigned to dept) AND (region within hierarchy)
            dept = getattr(worker, "department", None)
            if not dept or not getattr(dept, "head", None):
                return False
            if dept.head_id != user.id:
                return False

            # Category must be assigned to user's department
            if not self.category or not getattr(self.category, "assigned_department", None):
                return False
            issue_dept = self.category.assigned_department.department if self.category.assigned_department else None
            if not issue_dept or issue_dept.id != dept.id:
                return False

            # Administrative region must be same or descendant of worker's region
            if not self.administrative_region or not getattr(worker, "administrative_region", None):
                return False
            worker_region = worker.administrative_region
            issue_region = self.administrative_region

            if issue_region.id == worker_region.id:
                return True

            allowed_regions = worker_region.get_descendant_ids()
            return issue_region.id in allowed_regions
        except Exception:
            return False

    def has_edit_permission(self, user):
        return not hasattr(user, "governmentworker") or not self.assignee or self.assignee.id == user.id

    def get_internal_code(self):
        return f'{self.category.abbreviation}-{self.administrative_region.id}-{self.id}'

    def anonymize_issue_data(self):
        key = str(self.id)
        citizen = self.citizen
        if citizen:
            pdata, _ = Pdata.objects.get_or_create(key=key)
            data_encoded = cryptocode.encrypt(citizen.name, key)
            pdata.data = data_encoded
            pdata.save()
            citizen.name = "*"
            citizen.save()
        else:
            Pdata.objects.filter(key=key).delete()

        contact_information = self.contact_information
        if contact_information:
            contact = contact_information
            cdata, _ = Cdata.objects.get_or_create(key=key)
            data_encoded = cryptocode.encrypt(contact, key)
            cdata.data = data_encoded
            cdata.save()
            self.contact_information = "*"
        else:
            Cdata.objects.filter(key=key).delete()

    def get_assignee(self):
        region = self.administrative_region
        category = self.category
        department = category.assigned_department.department
        assignee = None
        if category.redirection_protocol:
            facilitator = Facilitator.objects.filter(administrative_region=region, village_secretary=1).first()
            if facilitator:
                assignee = facilitator.user

            if not assignee:
                related_workers = set(
                    GovernmentWorker.objects.filter(department=department, administrative_region=region).values_list(
                        "user", flat=True
                    )
                )

                assignees = (
                    User.objects.filter(assigned_issues__category__assigned_department__department=department)
                    .annotate(issue_count=Count('assigned_issues', distinct=True))
                    .order_by('issue_count')
                    .distinct()
                )

                department_workers_with_assignment = {worker.id for worker in assignees}
                department_workers_without_assignment = related_workers - department_workers_with_assignment

                if department_workers_without_assignment:
                    worker_id = list(department_workers_without_assignment)[0]
                    assignee = GovernmentWorker.objects.get(user=worker_id)
                else:
                    if assignees and related_workers:
                        for worker in assignees:
                            if worker.id in related_workers:
                                assignee = worker
                                break
                    elif related_workers:
                        assignee = GovernmentWorker.objects.filter(
                            department=department, administrative_region=region
                        ).first()
        else:
            print("not supposed to be here")
            assignee = department.head
        if not assignee:
            print(" definitively not supposed to be here")
            # TODO: ask about this repeated case
            facilitator = Facilitator.objects.filter(administrative_region=region, village_secretary=1).first()
            if facilitator:
                assignee = facilitator.user

        if category.confidentiality_level == "Confidential" and category.redirection_protocol == 0:
            facilitator = Facilitator.objects.filter(administrative_region=1, village_secretary=1).first()
            if facilitator:
                assignee = facilitator.user
                print("confidential assignee ok")
        return assignee

    def get_assignee_to_escalate(self, region):
        department = self.category.assigned_department.department
        parent = region.parent
        worker = GovernmentWorker.objects.filter(department=department, administrative_region=parent).first()
        if worker:
            return worker.user
        elif parent:
            return self.get_assignee_to_escalate(parent)
        else:
            return None

    def get_assignee_to_de_escalate(self, region):
        department = self.category.assigned_department.department
        children = region.children.all()
        worker = GovernmentWorker.objects.filter(department=department, administrative_region_id__in=children).first()
        if worker:
            return worker.user
        elif children:
            assignee = None
            for child in children:
                assignee = self.get_assignee_to_de_escalate(child)
                if assignee:
                    break
            return assignee
        else:
            return None


class Comment(models.Model):
    comment = models.TextField()
    user = models.ForeignKey(
        'authentication.User', blank=True, null=True, on_delete=models.CASCADE, related_name='comments'
    )
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='comments')
    due_date = models.DateTimeField(default=now)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Comment")
        verbose_name_plural = _("Comments")
        ordering = ['-due_date']

    def __str__(self):
        return f"{self.id} {self.comment}"


def issue_attachment_upload_path(instance, filename):
    filename, file_extension = os.path.splitext(filename)
    filename = f"{uuid.uuid()}{file_extension}"
    return f"attachments/{filename}"


class IssueAttachment(models.Model):
    external_id = models.CharField(
        max_length=255, verbose_name="couchDB document _id", default=None, null=True, blank=True
    )
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name='attachments', verbose_name=_('Issue'))
    file = models.FileField(
        upload_to=issue_attachment_upload_path, verbose_name='File', help_text=_('File attached to the issue')
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attachments',
        verbose_name=_('Uploaded by'),
    )
    created_date = models.DateTimeField(default=now, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))
    deleted_date = models.DateTimeField(null=True, blank=True, verbose_name=_('Deleted at'))

    class Meta:
        verbose_name = _('Issue Attachment')
        verbose_name_plural = _('Attachments')
        ordering = ['-created_date']
        indexes = [
            models.Index(fields=['issue', 'created_date']),
            models.Index(fields=['uploaded_by']),
        ]

    def __str__(self):
        return f"{self.filename} - Issue #{self.issue.id}"

    def delete(self, *args, **kwargs):
        """
        Delete the model instance and remove the underlying file using the storage API.
        This avoids accessing file.path which fails for storages that don't support absolute paths.
        """
        # Capture file name before deleting the model instance
        file_name = None
        try:
            if self.file:
                file_name = self.file.name
        except Exception:
            file_name = None

        # Delete the model instance first (so DB constraints are handled)
        super().delete(*args, **kwargs)

        # Then attempt to remove the file via storage API
        if not file_name:
            return

        storage = getattr(self.file, 'storage', default_storage)

        # Prefer storage.delete; guard against storages that raise NotImplementedError
        try:
            if storage.exists(file_name):
                storage.delete(file_name)
        except NotImplementedError:
            # Some test storages may not implement path-based operations; ignore deletion in that case
            pass
        except Exception:
            # Be conservative: don't let file deletion errors bubble up and break tests/views
            pass

    def save(self, *args, **kwargs):
        """
        Deletes the old file from the filesystem when updating the record
        with a new file.
        """
        # Use self.__class__ to query the database for the old instance
        if self.pk:
            try:
                old = self.__class__.objects.get(pk=self.pk)
            except self.__class__.DoesNotExist:
                old = None
        else:
            old = None

        super().save(*args, **kwargs)

        # If there was an old file and it is different from the new one, delete it
        if old and old.file and old.file != self.file:
            if os.path.isfile(old.file.path):
                os.remove(old.file.path)

    @property
    def filename(self):
        """
        Returns the original filename
        """
        return os.path.basename(self.file.name) if self.file else ''

    @property
    def file_extension(self):
        """
        Returns the file extension
        """
        return os.path.splitext(self.file.name)[1].lower() if self.file else ''

    @property
    def file_size(self):
        """
        Returns the file size in bytes
        """
        return self.file.size if self.file else 0

    @property
    def formatted_file_size(self):
        """
        Returns the formatted file size in English (MB, GB, etc.)
        """
        return filesizeformat_en(self.file_size)

    @property
    def file_type(self):
        """
        Returns the file MIME type
        """
        if not self.file:
            return ''

        import mimetypes

        mime_type, _ = mimetypes.guess_type(self.file.name)
        return mime_type or 'application/octet-stream'
