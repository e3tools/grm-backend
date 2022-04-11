import os

import shortuuid as uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from grm.utils import (
    belongs_to_region, get_parent_administrative_level, get_related_region_with_specific_level,
    sort_dictionary_list_by_field
)


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

    @property
    def name(self):
        return f'{self.first_name} {self.last_name}'


class GovernmentWorker(models.Model):
    user = models.OneToOneField('User', models.PROTECT)
    department = models.PositiveSmallIntegerField(db_index=True, verbose_name=_('department'))
    administrative_level = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_('administrative level'))

    class Meta:
        verbose_name = _('Government Worker')
        verbose_name_plural = _('Government Workers')

    @property
    def name(self):
        return self.user.name

    def has_read_permission_for_issue(self, eadl_db, issue):
        try:
            issue_administrative_id = issue['administrative_region']['administrative_id']
            if issue_administrative_id != self.administrative_level:
                issue_department_id = issue['category']['assigned_department']
                if self.department != issue_department_id:
                    return False
            belongs = belongs_to_region(eadl_db, issue_administrative_id, self.administrative_level)
            return belongs
        except Exception:
            return False


def get_government_worker_choices(empty_choice=True):
    query = GovernmentWorker.objects.select_related('user')
    choices = [(i.user.id, f'{i.user.first_name} {i.user.last_name}') for i in query]
    if empty_choice:
        choices = [('', '')] + choices
    return choices


def get_assignee(grm_db, eadl_db, issue_doc):
    try:
        doc_category = grm_db.get_query_result({
            "id": issue_doc['category']['id'],
            "type": 'issue_category'
        })[0][0]
    except Exception:
        raise

    department_id = doc_category['assigned_department']['id']

    if doc_category['redirection_protocol']:
        try:
            doc_administrative_level = eadl_db.get_query_result({
                "administrative_id": issue_doc['administrative_region']['administrative_id'],
                "type": 'administrative_level'
            })[0][0]
        except Exception:
            raise
        level = issue_doc['category']['administrative_level']
        related_region = get_related_region_with_specific_level(eadl_db, doc_administrative_level, level)

        startkey = [department_id, None, None]
        endkey = [department_id, {}, {}]
        assignments_result = grm_db.get_view_result(
            'issues', 'group_by_assignee', group=True, startkey=startkey, endkey=endkey)[:]
        administrative_level = related_region['administrative_id']
        related_workers = set(
            GovernmentWorker.objects.filter(
                department=department_id, administrative_level=administrative_level).values_list('user', flat=True))
        department_workers_with_assignment = {worker['key'][1] for worker in assignments_result}
        department_workers_without_assignment = related_workers - department_workers_with_assignment
        if department_workers_without_assignment:
            worker_id = list(department_workers_without_assignment)[0]
            worker_without_assignment = GovernmentWorker.objects.get(user=worker_id)
            assignee = {
                "id": worker_id,
                "name": worker_without_assignment.name
            }
        else:
            assignee = ""
            if assignments_result:
                assignments_result = sort_dictionary_list_by_field(assignments_result, 'value')
                for assignment in assignments_result:
                    worker_id = assignment['key'][1]
                    if worker_id in related_workers:
                        assignee = {
                            "id": worker_id,
                            "name": assignment['key'][2]
                        }
                        break
            elif related_workers:
                worker = GovernmentWorker.objects.filter(
                    department=department_id, administrative_level=administrative_level).first()
                assignee = {
                    "id": worker.user.id,
                    "name": worker.name
                }
    else:
        try:
            doc_department = grm_db.get_query_result({
                "id": department_id,
                "type": 'issue_department'
            })[0][0]
        except Exception:
            raise
        assignee = doc_department['head']
    if not assignee:
        try:
            adl_user = eadl_db.get_query_result({
                "administrative_level": issue_doc['category']['administrative_level'],
                "administrative_region": issue_doc['administrative_region']['administrative_id'],
                "village_secretary": 1,
                "type": 'adl'
            })[0][0]
            assignee = {
                "id": adl_user['_id'],
                "name": adl_user['representative']['name']
            }
        except Exception:
            pass
    return assignee


def get_assignee_to_escalate(eadl_db, department_id, administrative_id):
    try:
        parent = get_parent_administrative_level(eadl_db, administrative_id)
    except Exception:
        raise

    administrative_id = parent['administrative_id']
    worker = GovernmentWorker.objects.filter(department=department_id, administrative_level=administrative_id).first()
    if worker:
        assignee = {
            "id": worker.user.id,
            "name": worker.name
        }
        return assignee
    elif parent:
        return get_assignee_to_escalate(eadl_db, department_id, administrative_id)
