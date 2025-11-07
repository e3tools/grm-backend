import os

import shortuuid as uuid
from django.apps import apps
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


def photo_path(instance, filename):
    filename, file_extension = os.path.splitext(filename)
    filename = f"{uuid.uuid()}{file_extension}"
    return f"photos/{filename}"


class User(AbstractUser):
    email = models.EmailField(unique=True, verbose_name=_("email address"))
    phone_number = models.CharField(max_length=45, verbose_name=_("phone number"))
    photo = models.ImageField(upload_to=photo_path, blank=True, null=True, verbose_name=_("photo"))
    external_id = models.CharField(max_length=255, verbose_name="couchDB document _id", default=None, null=True)
    grm_manager = models.BooleanField(default=False)
    grm_owner = models.BooleanField(default=False)

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = str(uuid.uuid())

        if self.pk:
            try:
                old = self.__class__.objects.get(pk=self.pk)
            except self.__class__.DoesNotExist:
                old = None
        else:
            old = None

        super().save(*args, **kwargs)

        # If there was an old photo and it is different from the new one, delete it
        if old and old.photo and old.photo != self.photo:
            if os.path.isfile(old.photo.path):
                os.remove(old.photo.path)

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    def delete(self, *args, **kwargs):
        if self.photo:
            if os.path.isfile(self.photo.path):
                os.remove(self.photo.path)
        super().delete(*args, **kwargs)


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
    user = models.OneToOneField(User, models.PROTECT)
    department = models.ForeignKey("issues.IssueDepartment", on_delete=models.CASCADE, verbose_name=_("department"))
    administrative_region = models.ForeignKey(
        "issues.AdministrativeRegion",
        on_delete=models.CASCADE,
        verbose_name=_("administrative region"),
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


class Facilitator(models.Model):
    user = models.OneToOneField(User, models.PROTECT)
    administrative_region = models.ForeignKey(
        "issues.AdministrativeRegion", on_delete=models.CASCADE, related_name='facilitators'
    )
    unique_region = models.BooleanField(null=True)
    village_secretary = models.BooleanField(null=True)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Facilitator")
        verbose_name_plural = _("Facilitators")

    @property
    def name(self):
        return self.user.name


class Citizen(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)
    citizen = models.OneToOneField("issues.Citizen", on_delete=models.CASCADE, related_name="user_citizen", unique=True)
    created_date = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_date = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))

    class Meta:
        verbose_name = _("Citizen")
        verbose_name_plural = _("Citizens")

    @property
    def name(self):
        return self.user.name

    def save(self, *args, **kwargs):
        if self.citizen_id is None:
            IssuesCitizen = apps.get_model('issues', 'Citizen')
            self.citizen = IssuesCitizen.objects.create(name=self.user.name)

        super().save(*args, **kwargs)
