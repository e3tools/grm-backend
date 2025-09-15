import os

import cryptocode
import shortuuid as uuid
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, models
from django.db.models import Count
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from authentication.models import Cdata, Facilitator, GovernmentWorker, Pdata, User
from grm.constants import (
    ALERT_CHOICE,
    ALERT_CHOICES,
    ANONYMOUS_CHOICE,
    CITIZEN_GROUP_CHOICES,
    CITIZEN_TYPE_CHOICES,
    CONTACT_CHOICES,
    CONTACT_MEDIUM_ERROR_MESSAGE,
    GENDER_CHOICES,
    MEDIUM_CHOICES,
)
from grm.utils import filesizeformat_en, get_choices


class AdministrativeLevel(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

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
        while parent.parent:
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
    name = models.CharField(max_length=100)
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

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)


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
    name = models.CharField(max_length=255, unique=True)
    final_status = models.BooleanField(default=False)
    initial_status = models.BooleanField(default=False)
    rejected_status = models.BooleanField(default=False)
    open_status = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Issue Status")
        verbose_name_plural = _("Issue Status")
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)


class IssueDepartment(models.Model):
    name = models.CharField(max_length=255, unique=True)
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


class IssueSubType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', db_index=True
    )
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Issue Subtype")
        verbose_name_plural = _("Issue Subtypes")
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)


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
    parent = models.ForeignKey(IssueSubType, blank=True, null=True, on_delete=models.CASCADE, related_name='categories')
    confidentiality_level = models.CharField(max_length=255, null=True, blank=True)
    redirection_protocol = models.IntegerField(default=0)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Issue Category")
        verbose_name_plural = _("Issue Categories")
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls, empty_choice=True):
        return get_choices(cls.objects.all(), empty_choice)


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
    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=50, blank=True, choices=CITIZEN_GROUP_CHOICES)
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
    type = models.CharField(max_length=50, null=True, blank=True, choices=CITIZEN_TYPE_CHOICES)
    gender = models.CharField(max_length=50, null=True, blank=True, choices=GENDER_CHOICES)
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
    contact_medium = models.CharField(max_length=50, blank=True, choices=MEDIUM_CHOICES, default=ANONYMOUS_CHOICE)
    contact_method = models.CharField(max_length=255, choices=CONTACT_CHOICES, default=None, null=True, blank=True)
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
    alert_message_status = models.CharField(max_length=50, blank=True, default="", choices=ALERT_CHOICES)
    reject_flag = models.BooleanField(default=False)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=0)
    escalation_reason = models.TextField(null=True, blank=True)
    appeal_status = models.BooleanField(default=False)

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
        self._validate_contact_method_based_on_contact_medium()
        return super().save(*args, **kwargs)

    def _validate_contact_method_based_on_contact_medium(self):
        if self.contact_medium == ALERT_CHOICE and not self.contact_method:
            raise ValidationError(CONTACT_MEDIUM_ERROR_MESSAGE)

    def resolution_days(self):
        if self.resolution_date is not None:
            return abs((self.resolution_date - self.intake_date).days)
        return None

    def is_piu_staff(self, user):
        try:
            head = self.category.assigned_department.department.head
        except Exception:
            head = None
        return user.id == self.assignee.id or (head and user.id == head.id)

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
        department = self.assignee.governmentworker.department
        parent = region.parent
        region = parent
        worker = GovernmentWorker.objects.filter(
            department=int(department.id + 1), administrative_region=region
        ).first()
        if worker:
            facilitator = Facilitator.objects.filter(
                user=worker.user, administrative_region=region, department=worker.department
            ).first()
            if facilitator:
                return facilitator.user

        elif parent:
            return self.get_assignee_to_escalate(region)


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
        Deletes the file when the record is deleted
        """
        if self.file:
            if os.path.isfile(self.file.path):
                os.remove(self.file.path)
        super().delete(*args, **kwargs)

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
