import json

import pytest
from django.test import TestCase, override_settings

from authentication.factories import UserFactory
from grm.constants import COMPLETED_CHOICE
from grm.utils import reset_sequences
from issues.factories import AdministrativeRegionFactory
from wizard.models import WizardSection

JSON_TYPE = "application/json"
URLENCODED_TYPE = "application/x-www-form-urlencoded"
AJAX_HEADER = "HTTP_X_REQUESTED_WITH"
AJAX_HEADER_VALUE = "XMLHttpRequest"


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='en-us')
class ViewTestCase(TestCase):
    content_type = URLENCODED_TYPE
    user = None

    def setUp(self):
        reset_sequences()
        super().setUp()

    @staticmethod
    def create_user(is_active=True, **kwargs):
        return UserFactory(is_active=is_active)

    def authenticate(self, user):
        self.user = self.create_user() if not self.user else self.user
        request_user = user if user else self.user
        self.client.force_login(user=request_user)

    def get(self, uri, data=None, authorized=True, user=None, ajax=None, **kwargs):
        if authorized:
            self.authenticate(user)
        if ajax:
            kwargs[AJAX_HEADER] = AJAX_HEADER_VALUE
        return self.client.get(uri, data, **kwargs)

    def put(self, uri, data, authorized=True, user=None, ajax=None, **kwargs):
        self.client.logout()
        if authorized:
            self.authenticate(user)
        if self.content_type == JSON_TYPE:
            data = json.dumps(data)
            kwargs["content_type"] = self.content_type
        if ajax:
            kwargs[AJAX_HEADER] = AJAX_HEADER_VALUE
        return self.client.put(uri, data, **kwargs)

    def patch(self, uri, data, authorized=True, user=None, ajax=None, **kwargs):
        self.client.logout()
        if authorized:
            self.authenticate(user)
        if self.content_type == JSON_TYPE:
            data = json.dumps(data)
            kwargs["content_type"] = self.content_type
        if ajax:
            kwargs[AJAX_HEADER] = AJAX_HEADER_VALUE
        return self.client.patch(uri, data, **kwargs)

    def post(self, uri, data, authorized=True, user=None, ajax=None, **kwargs):
        self.client.logout()
        if authorized:
            self.authenticate(user)
        if self.content_type == JSON_TYPE:
            if "format" not in kwargs:
                data = json.dumps(data)
                kwargs["content_type"] = self.content_type
        if ajax:
            kwargs[AJAX_HEADER] = AJAX_HEADER_VALUE
        return self.client.post(uri, data, **kwargs)

    def delete(self, uri, authorized=True, user=None, ajax=None, **kwargs):
        self.client.logout()
        if authorized:
            self.authenticate(user)
        if ajax:
            kwargs[AJAX_HEADER] = AJAX_HEADER_VALUE
        return self.client.delete(uri, **kwargs)


class DashboardTestCase(ViewTestCase):

    def setUp(self):
        WizardSection.objects.update(status=COMPLETED_CHOICE)
        root_region = AdministrativeRegionFactory()
        AdministrativeRegionFactory(parent=root_region)
        super().setUp()
