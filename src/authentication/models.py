import os

import shortuuid as uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


def photo_path(instance, filename):
    filename, file_extension = os.path.splitext(filename)
    filename = '{}{}'.format(uuid.uuid(), file_extension)
    return 'photos/{}'.format(filename)


class User(AbstractUser):
    email = models.EmailField(unique=True, verbose_name=_('email address'))
    phone_number = models.CharField(max_length=45, verbose_name=_('phone number'))
    photo = models.ImageField(upload_to=photo_path, blank=True, null=True, verbose_name=_('photo'))

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = str(uuid.uuid())
        return super().save(*args, **kwargs)

    def get_name(self):
        return f'{self.first_name} {self.last_name}'


class GovernmentWorker(models.Model):
    user = models.OneToOneField('User', models.PROTECT)
    department = models.PositiveSmallIntegerField(db_index=True, verbose_name=_('department'))
    administrative_level = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_('administrative level'))

    class Meta:
        verbose_name = _('Government Worker')
        verbose_name_plural = _('Government Workers')

    def get_name(self):
        return self.user.get_name()
