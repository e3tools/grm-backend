from django.conf import settings
from parameterized import parameterized
from rest_framework.reverse import reverse

from authentication.tests import IssueFactory
from client import COUCHDB_PASSWORD, COUCHDB_USERNAME
from grm.tests import BaseTestCase


class TestUploadIssueAttachmentAPIView(BaseTestCase):
    error_messages = {
        'credentials': 'Unauthorized access with the credentials provided.',
        'not_found': 'Not found.',
        'blank': 'This field may not be blank.',
        'invalid_file': 'The submitted data was not a file. Check the encoding type on the form.',
        'required_field': 'This field is required.',
        'required_file': 'No file was submitted.',
        'file_size': 'Select a file size less than or equal to %(max_size)s. The selected file size is %(size)s.'
    }

    def setUp(self):
        super().setUp()
        self.url = reverse('attachments:upload-issue-attachment')

    @parameterized.expand([
        ('wrong_username', 'wrong_password'),
        (COUCHDB_USERNAME, 'wrong_password'),
        ('wrong_username', COUCHDB_PASSWORD),
    ])
    def test_auth_permission(self, username, password):
        doc = IssueFactory().doc
        attachment = doc['attachments'][0]
        input_data = {
            'username': username,
            'password': password,
            'doc_id': doc['_id'],
            'attachment_id': attachment['id'],
            'file': self.create_file(),
        }

        response = self.post(self.url, input_data, authorized=False, format='multipart')
        data = response.data

        assert response.status_code == 400
        assert len(data) == 1
        assert str(data['non_field_errors'][0]) == self.error_messages['credentials']

    def test_successful_upload(self):
        doc = IssueFactory().doc
        file = self.create_file()
        attachment = doc['attachments'][0]
        input_data = {
            'username': COUCHDB_USERNAME,
            'password': COUCHDB_PASSWORD,
            'doc_id': doc['_id'],
            'attachment_id': attachment['id'],
            'file': file,
        }

        assert attachment['url'] == ""
        assert attachment['uploaded'] is False

        with self.assertNumQueries(7):
            response = self.post(self.url, input_data, authorized=False, format='multipart')
        data = response.data
        file_name = file.name.split('/')[-1]
        doc_attachment = self.eadl_db[data['id']]
        updated_doc = self.eadl_db[doc['_id']]
        updated_attachment = updated_doc['attachments'][0]

        assert response.status_code == 201
        assert len(data) == 3
        assert data['ok'] is True
        assert data['id'] == doc_attachment['_id']
        assert data['rev'] == doc_attachment['_rev']
        assert file_name in doc_attachment['_attachments']
        assert updated_attachment['url'] == f"/grm_attachments/{data['id']}/{file_name}"
        assert updated_attachment['uploaded'] is True
        attachment['url'] = updated_attachment['url']
        attachment['uploaded'] = updated_attachment['uploaded']
        attachment['bd_id'] = data['id']
        assert attachment == updated_attachment

    def test_non_existent_doc_id(self):
        doc = IssueFactory().doc
        attachment = doc['attachments'][0]
        input_data = {
            'username': COUCHDB_USERNAME,
            'password': COUCHDB_PASSWORD,
            'doc_id': 'non_existent_doc_id',
            'attachment_id': attachment['id'],
            'file': self.create_file(),
        }

        response = self.post(self.url, input_data, authorized=False, format='multipart')
        data = response.data

        assert response.status_code == 404
        assert len(data) == 1
        assert str(data['detail']) == self.error_messages['not_found']

    def test_non_existent_attachment_id(self):
        doc = IssueFactory().doc
        input_data = {
            'username': COUCHDB_USERNAME,
            'password': COUCHDB_PASSWORD,
            'doc_id': doc['_id'],
            'attachment_id': 'non_existent_attachment_id',
            'file': self.create_file(),
        }

        response = self.post(self.url, input_data, authorized=False, format='multipart')
        data = response.data

        assert response.status_code == 404
        assert len(data) == 1
        assert str(data['detail']) == self.error_messages['not_found']

    def test_empty_field(self):
        input_data = {
            'username': '',
            'password': '',
            'doc_id': '',
            'attachment_id': '',
            'file': '',
        }

        response = self.post(self.url, input_data, authorized=False, format='multipart')
        data = response.data

        assert response.status_code == 400
        assert set(data.keys()) == {'username', 'password', 'file', 'doc_id', 'attachment_id'}
        for k in {'username', 'password', 'doc_id', 'attachment_id'}:
            assert str(data[k][0]) == self.error_messages['blank']
        assert str(data['file'][0]) == self.error_messages['invalid_file']

    def test_empty_data(self):
        response = self.post(self.url, {}, authorized=False, format='multipart')
        data = response.data

        assert response.status_code == 400
        assert set(data.keys()) == {'username', 'password', 'file', 'doc_id', 'attachment_id'}
        for k in data:
            if k != 'file':
                assert str(data[k][0]) == self.error_messages['required_field']
        assert str(data['file'][0]) == self.error_messages['required_file']

    @parameterized.expand([
        ('5.0 MB', settings.MAX_UPLOAD_SIZE),
        ('5.1 MB', settings.MAX_UPLOAD_SIZE + int(0.1 * 1024 * 1024)),
    ])
    def test_file_size(self, size_representation, size):
        doc = IssueFactory().doc
        attachment = doc['attachments'][0]
        file = self.create_file(size)
        input_data = {
            'username': COUCHDB_USERNAME,
            'password': COUCHDB_PASSWORD,
            'doc_id': doc['_id'],
            'attachment_id': attachment['id'],
            'file': file,
        }

        response = self.post(self.url, input_data, authorized=False, format='multipart')
        data = response.data

        if size_representation == '5.0 MB':
            assert response.status_code == 201
        else:
            assert response.status_code == 400
            assert len(data) == 1
            assert str(data['file'][0]) == self.error_messages['file_size'] % {'max_size': '5.0\xa0MB',
                                                                               'size': '5.1\xa0MB'}
