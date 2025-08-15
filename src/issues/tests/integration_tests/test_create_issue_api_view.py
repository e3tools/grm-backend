import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from unittest.mock import patch

from grm.utils import reset_sequences
from issues.factories import (
    AdministrativeRegionFactory,
    IssueCategoryFactory,
    IssueStatusFactory,
    IssueTypeFactory,
    UserFactory,
    CitizenFactory,
    ComponentFactory,
    SubComponentFactory,
)
from issues.models import Issue


@pytest.mark.django_db
class TestIssueCreateAPIView(APITestCase):
    """
    Test suite for the IssueCreateAPIView.

    This class tests the API endpoint for creating a new issue,
    covering successful creation, authentication, validation errors,
    and server-side error handling.
    """

    def setUp(self):
        """
        Set up the necessary data for the tests.
        """
        self.url = reverse("issues:create-issue")
        reset_sequences()

        # Create user and token for authentication
        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)

        # Create related objects using factories
        self.status = IssueStatusFactory()
        self.category = IssueCategoryFactory()
        self.issue_type = IssueTypeFactory()
        self.administrative_region = AdministrativeRegionFactory()
        self.reporter = self.user
        self.assignee = UserFactory()
        self.citizen = CitizenFactory()
        self.component = ComponentFactory(description="This is a description")
        self.sub_component = SubComponentFactory()
        self.citizen.id = None
        # Define a valid payload for a POST request
        self.valid_payload = {
            'title': 'Test Issue Title',
            'description': 'This is a test issue description.',
            'status': self.status.id,
            'category': self.category.id,
            'issue_type': self.issue_type.id,
            'administrative_region': self.administrative_region.id,
            'reporter': self.reporter.id,
            'assignee': self.assignee.id,
            'citizen': self.citizen,
            'component': self.component.id,
            'sub_component': self.sub_component.id,
            'contact_medium': 'facilitator',
            'contact_method': 'email',
            'contact_information': 'test@example.com',
            'ongoing_issue': False,
            'tracking_code': 'ABC-123-XYZ'
        }

    def authenticate_with_token(self):
        """Helper method to authenticate the client with the user's token."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    # --- Test Authentication ---

    def test_authentication_required_for_creation(self):
        """
        Test that a request without credentials is rejected with 401 Unauthorized.
        """
        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Authentication credentials were not provided.", str(response.data))

    def test_invalid_token_rejects_request(self):
        """
        Test that a request with an invalid token is rejected with 401 Unauthorized.
        """
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid_token_xyz')
        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("Invalid token.", str(response.data))

    def test_inactive_user_cannot_create_issue(self):
        """
        Test that an inactive user cannot create an issue.
        """
        inactive_user = UserFactory(is_active=False)
        inactive_token = Token.objects.create(user=inactive_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {inactive_token.key}')

        response = self.client.post(self.url, self.valid_payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("User inactive or deleted.", str(response.data))

    # --- Test Successful Creation ---

    def test_successful_issue_creation(self):
        """
        Test that a valid payload successfully creates a new issue.
        """
        self.authenticate_with_token()

        # Check the initial count of issues
        initial_issue_count = Issue.objects.count()

        response = self.client.post(self.url, self.valid_payload, format='json')

        # Check the response status and content
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'Issue created successfully.')
        self.assertIn('data', response.data)

        # Verify that an issue was created in the database
        self.assertEqual(Issue.objects.count(), initial_issue_count + 1)

        # Verify the data in the database
        created_issue = Issue.objects.get(title='Test Issue Title')
        self.assertEqual(created_issue.description, 'This is a test issue description.')
        self.assertEqual(created_issue.status.id, self.status.id)
        self.assertEqual(created_issue.category.id, self.category.id)
        self.assertEqual(created_issue.issue_type.id, self.issue_type.id)
        self.assertEqual(created_issue.administrative_region.id, self.administrative_region.id)
        self.assertEqual(created_issue.reporter.id, self.reporter.id)
        self.assertEqual(created_issue.assignee.id, self.assignee.id)

        # Verify the response data matches the created object
        response_data = response.data['data']
        self.assertEqual(response_data['title'], 'Test Issue Title')
        self.assertEqual(response_data['description'], 'This is a test issue description.')
        self.assertEqual(response_data['status']['id'], self.status.id)
        self.assertEqual(response_data['category']['id'], self.category.id)
        self.assertEqual(response_data['issue_type']['id'], self.issue_type.id)
        self.assertEqual(response_data['administrative_region']['administrative_id'],
                         str(self.administrative_region.id))

    # --- Test Validation Errors (400 Bad Request) ---

    def test_missing_required_fields_returns_400(self):
        """
        Test that a request with missing required fields returns 400 Bad Request.
        """
        self.authenticate_with_token()

        # Create an invalid payload with missing fields
        invalid_payload = self.valid_payload.copy()
        del invalid_payload['status']
        del invalid_payload['category']
        del invalid_payload['issue_type']

        response = self.client.post(self.url, invalid_payload, format='json')

        # Check the response status and error messages
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], 'Validation failed.')
        self.assertIn('errors', response.data)
        self.assertIn('status', response.data['errors'])
        self.assertIn('category', response.data['errors'])
        self.assertIn('issue_type', response.data['errors'])

    def test_invalid_foreign_key_id_returns_400(self):
        """
        Test that a request with a non-existent foreign key ID returns 400.
        """
        self.authenticate_with_token()

        # Use an invalid ID for a foreign key field
        invalid_payload = self.valid_payload.copy()
        invalid_payload['status'] = 99999  # A non-existent ID

        response = self.client.post(self.url, invalid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data['errors'])
        self.assertIn('Invalid pk', str(response.data['errors']['status']))

    def test_contact_method_validation_error(self):
        """
        Test custom validation for contact_method and contact_medium.
        """
        self.authenticate_with_token()

        # Case 1: contact_medium is not 'channel-alert' and contact_method is missing
        invalid_payload = self.valid_payload.copy()
        invalid_payload['contact_medium'] = 'facilitator'
        invalid_payload['contact_method'] = None

        response = self.client.post(self.url, invalid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('contact_method', response.data['errors'])
        self.assertIn('You must define the contact method if your contact medium is not channel alert', str(response.data['errors']['contact_method']))

        # Case 2: contact_medium is 'channel-alert' and contact_method is None (this should pass)
        valid_payload_channel_alert = self.valid_payload.copy()
        valid_payload_channel_alert['contact_medium'] = 'channel-alert'
        valid_payload_channel_alert['contact_method'] = None

        response = self.client.post(self.url, valid_payload_channel_alert, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # --- Test Server-Side Error (500 Internal Server Error) ---

    @patch('issues.serializers.IssueCreateSerializer.save')
    def test_server_error_returns_500(self, mock_save):
        """
        Test that a server-side error during the save process returns 500.
        """
        self.authenticate_with_token()

        # Mock the save method to raise an unexpected exception
        mock_save.side_effect = Exception("Simulated database error")

        response = self.client.post(self.url, self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data['message'], 'An error occurred while creating the issue.')
        self.assertEqual(response.data['error'], 'Simulated database error')
