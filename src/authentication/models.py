import os

import cryptocode
import shortuuid as uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from issues.models import AdministrativeRegion, IssueDepartment


def photo_path(instance, filename):
    filename, file_extension = os.path.splitext(filename)
    filename = f"{uuid.uuid()}{file_extension}"
    return f"photos/{filename}"


class User(AbstractUser):
    email = models.EmailField(unique=True, verbose_name=_("email address"))
    phone_number = models.CharField(max_length=45, verbose_name=_("phone number"))
    photo = models.ImageField(upload_to=photo_path, blank=True, null=True, verbose_name=_("photo"))
    external_id = models.CharField(max_length=255, verbose_name="couchDB document _id", default=None, null=True)

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = str(uuid.uuid())
        return super().save(*args, **kwargs)

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"


class AbstractKeyData(models.Model):
    key = models.CharField(max_length=255, primary_key=True, unique=True)
    data = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        abstract = True


class Pdata(AbstractKeyData):
    """Used to anonymize citizen information"""

    class Meta:
        verbose_name_plural = "Pdata"

    def __str__(self):
        return f"{self.key}: {self.data}"


class Cdata(AbstractKeyData):
    """Used to anonymize contact information"""

    class Meta:
        verbose_name_plural = "Cdata"

    def __str__(self):
        return f"{self.key}: {self.data}"


class GovernmentWorker(models.Model):
    user = models.OneToOneField("User", models.PROTECT)
    department = models.ForeignKey(IssueDepartment, on_delete=models.CASCADE, verbose_name=_("department"))
    administrative_region = models.ForeignKey(
        AdministrativeRegion, blank=True, null=True, on_delete=models.CASCADE, verbose_name=_("administrative region")
    )

    class Meta:
        verbose_name = _("Government Worker")
        verbose_name_plural = _("Government Workers")

    @property
    def name(self):
        return self.user.name

    def has_read_permission_for_issue(self, issue):
        try:
            administrative_region = issue.administrative_region
            if (
                administrative_region != self.administrative_region
                and issue.category.assigned_department != self.department
            ):
                return False
            belongs = administrative_region.belongs_to_region(self.administrative_region)
            return belongs
        except Exception:
            return False

    @classmethod
    def get_choices(cls, empty_choice=True):
        query = cls.objects.select_related("user")
        choices = [(i.user.id, f"{i.user.first_name} {i.user.last_name}") for i in query]
        if empty_choice:
            choices = [("", "")] + choices
        return choices


def get_assignee(issue, region_id=None):
    category = issue.category
    assigned_department = category.assigned_department
    department_id = assigned_department.id
    assignee = None
    if category.redirection_protocol:
        if not region_id:
            level = issue.category.assigned_department.administrative_level
            related_region = issue.administrative_region.get_ancestor_with_level(level)
            region_id = related_region.region_id

        if region_id:
            facilitator = Facilitator.objects.filter(administrative_region=region_id, village_secretary=1).first()
            if facilitator:
                assignee = facilitator.user

        if not assignee:
            related_workers = set(
                GovernmentWorker.objects.filter(department=department_id, administrative_region=region_id).values_list(
                    "user", flat=True
                )
            )

            assignees = (
                User.objects.filter(assigned_issues__category__assigned_department_id=department_id)
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
                        department=department_id, administrative_region=region_id
                    ).first()
    else:
        print("not supposed to be here")
        assignee = assigned_department.department.head
    if not assignee:
        print(" definitively not supposed to be here")
        # TODO: ask about this repeated case
        facilitator = Facilitator.objects.filter(administrative_region=region_id, village_secretary=1).first()
        if facilitator:
            assignee = facilitator.user

    if category.confidentiality_level == "Confidential" and category.redirection_protocol == 0:
        facilitator = Facilitator.objects.filter(administrative_region=1, village_secretary=1).first()
        if facilitator:
            assignee = facilitator.user
            print("confidential assignee ok")
    return assignee


def get_assignee_to_escalate(department_id, region_id):
    parent = AdministrativeRegion.objects.get(id=region_id).parent
    region_id = parent.id
    worker = GovernmentWorker.objects.filter(department=int(department_id + 1), administrative_region=region_id).first()
    if worker:
        facilitator = Facilitator.objects.filter(
            user=worker.user, administrative_region=region_id, department=worker.department
        ).first()
        if facilitator:
            return facilitator.user

    elif parent:
        return get_assignee_to_escalate(department_id, region_id)


def anonymize_issue_data(issue):
    key = str(issue.id)
    citizen = issue.citizen
    if citizen:
        pdata, _ = Pdata.objects.get_or_create(key=key)
        data_encoded = cryptocode.encrypt(citizen.name, key)
        pdata.data = data_encoded
        pdata.save()
        citizen.name = "*"
        citizen.save()
    else:
        Pdata.objects.filter(key=key).delete()

    contact_information = issue.contact_information
    if contact_information:
        contact = contact_information
        cdata, _ = Cdata.objects.get_or_create(key=key)
        data_encoded = cryptocode.encrypt(contact, key)
        cdata.data = data_encoded
        cdata.save()
        issue.contact_information = "*"
    else:
        Cdata.objects.filter(key=key).delete()


class Facilitator(models.Model):
    user = models.OneToOneField("User", models.PROTECT)
    department = models.ForeignKey(
        IssueDepartment, blank=True, null=True, on_delete=models.CASCADE, related_name='departments'
    )
    administrative_region = models.ForeignKey(
        AdministrativeRegion, blank=True, null=True, on_delete=models.CASCADE, related_name='facilitators'
    )
    unique_region = models.BooleanField(null=True)
    village_secretary = models.BooleanField(null=True)

    class Meta:
        verbose_name = _("Facilitator")
        verbose_name_plural = _("Facilitators")

    @property
    def name(self):
        return self.user.name
