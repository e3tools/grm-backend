from unittest.mock import patch

from django.urls import reverse

from authentication.factories import (
    FacilitatorFactory,
    GovernmentWorkerFactory,
    UserFactory,
)
from grm.tests.base import DashboardTestCase


class SendBulkNotificationAPIViewTest(DashboardTestCase):
    """Tests for SendBulkNotificationAPIView (AJAX endpoint to send bulk notifications)."""

    def setUp(self):
        super().setUp()
        self.manager = UserFactory(grm_manager=True)
        self.normal_user = UserFactory()
        self.url = reverse("dashboard:performance_diagnostics:api_send_bulk_notification")
        self.content_type = "application/json"

        # Create test users
        self.user_with_email = UserFactory(phone_number="", first_name="John", last_name="Doe")
        GovernmentWorkerFactory(user=self.user_with_email, administrative_region=self.root_region)

        self.user_with_phone = UserFactory()
        FacilitatorFactory(user=self.user_with_phone, administrative_region=self.root_region)

        self.user_with_both = UserFactory()
        GovernmentWorkerFactory(user=self.user_with_both, administrative_region=self.root_region)

        self.user_no_contact = UserFactory(
            email="",
            phone_number="",
        )

    @patch('dashboard.services.send_mail_notification')
    def test_send_email_notifications_success(self, mock_send_mail):
        """API should successfully send email notifications to users with email addresses."""
        mock_send_mail.return_value = None  # Simulate successful email send

        data = {
            'user_ids': [self.user_with_email.id, self.user_with_both.id],
            'notification_type': 'email',
            'message': 'Please check your assigned issues.',
        }

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        response_data = resp.json()

        assert 'msg' in response_data
        assert mock_send_mail.call_count == 2

    @patch('dashboard.services.send_sms')
    def test_send_sms_notifications_success(self, mock_send_sms):
        """API should successfully send SMS notifications to users with phone numbers."""
        mock_send_sms.return_value = None  # Simulate successful SMS send

        data = {
            'user_ids': [self.user_with_phone.id, self.user_with_both.id],
            'notification_type': 'sms',
            'message': 'Please check your assigned issues.',
        }

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        response_data = resp.json()

        assert 'msg' in response_data
        assert mock_send_sms.call_count == 2

    @patch('dashboard.services.send_mail_notification')
    @patch('dashboard.services.send_sms')
    def test_send_both_email_and_sms(self, mock_send_sms, mock_send_mail):
        """API should send both email and SMS when notification_type is 'email_and_sms'."""
        mock_send_mail.return_value = None
        mock_send_sms.return_value = None

        data = {
            'user_ids': [self.user_with_both.id],
            'notification_type': 'email_and_sms',
            'message': 'Please check your assigned issues.',
        }

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        response_data = resp.json()

        assert 'msg' in response_data
        assert mock_send_mail.call_count == 1
        assert mock_send_sms.call_count == 1

    @patch('dashboard.services.send_mail_notification')
    def test_skip_users_without_email(self, mock_send_mail):
        """API should skip users without email addresses when sending emails."""
        mock_send_mail.return_value = None

        data = {
            'user_ids': [self.user_with_email.id, self.user_no_contact.id],  # Second user has no email
            'notification_type': 'email',
            'message': 'Test message',
        }

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        # Should only send 1 email (to user_with_email)
        assert mock_send_mail.call_count == 1

    @patch('dashboard.services.send_sms')
    def test_skip_users_without_phone(self, mock_send_sms):
        """API should skip users without phone numbers when sending SMS."""
        mock_send_sms.return_value = None

        data = {
            'user_ids': [self.user_with_phone.id, self.user_with_email.id],  # Second user has no phone
            'notification_type': 'sms',
            'message': 'Test message',
        }

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        # Should only send 1 SMS (to user_with_phone)
        assert mock_send_sms.call_count == 1

    @patch('dashboard.services.send_mail_notification')
    def test_email_send_failure(self, mock_send_mail):
        """API should handle email send failures gracefully."""
        mock_send_mail.side_effect = Exception("SMTP connection failed")

        data = {'user_ids': [self.user_with_email.id], 'notification_type': 'email', 'message': 'Test message'}

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        # Should return error but not crash
        assert resp.status_code == 400
        response_data = resp.json()
        assert 'msg' in response_data

    @patch('dashboard.services.send_sms')
    def test_sms_send_failure(self, mock_send_sms):
        """API should handle SMS send failures gracefully."""
        mock_send_sms.side_effect = Exception("Twilio API error")

        data = {'user_ids': [self.user_with_phone.id], 'notification_type': 'sms', 'message': 'Test message'}

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        # Should return error but not crash
        assert resp.status_code == 400
        response_data = resp.json()
        assert 'msg' in response_data

    @patch('dashboard.services.send_mail_notification')
    def test_partial_success_with_failures(self, mock_send_mail):
        """API should report partial success when some notifications fail."""
        # First call succeeds, second call fails
        mock_send_mail.side_effect = [None, Exception("Failed")]

        data = {
            'user_ids': [self.user_with_email.id, self.user_with_both.id],
            'notification_type': 'email',
            'message': 'Test message',
        }

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        response_data = resp.json()
        assert 'msg' in response_data
        # Should indicate partial success

    def test_empty_user_ids_returns_error(self):
        """API should return error when no user IDs provided."""
        data = {'user_ids': [], 'notification_type': 'email', 'message': 'Test message'}

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 400
        response_data = resp.json()
        assert 'msg' in response_data

    def test_invalid_notification_type(self):
        """API should return error for invalid notification type."""
        data = {'user_ids': [self.user_with_email.id], 'notification_type': 'invalid_type', 'message': 'Test message'}

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 400
        response_data = resp.json()
        assert 'msg' in response_data

    def test_empty_message_returns_error(self):
        """API should return error when message is empty."""
        data = {'user_ids': [self.user_with_email.id], 'notification_type': 'email', 'message': ''}

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 400
        response_data = resp.json()
        assert 'msg' in response_data

    def test_whitespace_only_message_returns_error(self):
        """API should return error when message contains only whitespace."""
        data = {'user_ids': [self.user_with_email.id], 'notification_type': 'email', 'message': '   \n\t   '}

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 400
        response_data = resp.json()
        assert 'msg' in response_data

    @patch('dashboard.services.send_mail_notification')
    @patch('dashboard.services.send_sms')
    def test_all_users_skipped_no_contact_info(self, mock_send_sms, mock_send_mail):
        """API should return error when all users lack required contact information."""
        data = {'user_ids': [self.user_no_contact.id], 'notification_type': 'email', 'message': 'Test message'}

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 400
        response_data = resp.json()
        assert 'msg' in response_data
        # Should not call send functions
        assert mock_send_mail.call_count == 0
        assert mock_send_sms.call_count == 0

    @patch('dashboard.services.send_sms')
    def test_sms_message_truncation(self, mock_send_sms):
        """API should truncate SMS messages to 160 characters."""
        mock_send_sms.return_value = None

        long_message = 'A' * 200  # 200 character message

        data = {'user_ids': [self.user_with_phone.id], 'notification_type': 'sms', 'message': long_message}

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        # Verify SMS was sent with truncated message
        assert mock_send_sms.called
        call_args = mock_send_sms.call_args
        sent_message = call_args.kwargs['body']
        assert len(sent_message) <= 160

    def test_invalid_json_returns_error(self):
        """API should return error for invalid JSON in request body."""
        resp = self.client.post(
            self.url, data='invalid json{', content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.client.force_login(self.manager)

        resp = self.client.post(
            self.url, data='invalid json{', content_type='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        assert resp.status_code == 400

    def test_access_denied_for_non_manager(self):
        """Non-GRM Manager should be forbidden from sending notifications."""
        data = {'user_ids': [self.user_with_email.id], 'notification_type': 'email', 'message': 'Test message'}

        resp = self.post(self.url, data=data, user=self.normal_user, ajax=True)
        assert resp.status_code == 403

    def test_non_ajax_request_returns_404(self):
        """Non-AJAX requests should return 404."""
        data = {'user_ids': [self.user_with_email.id], 'notification_type': 'email', 'message': 'Test message'}

        resp = self.post(self.url, data=data, user=self.manager, ajax=False)
        assert resp.status_code == 404

    def test_post_forbidden_for_unauthenticated(self):
        """
        Requests without authentication should be rejected.
        The mixin used returns 404 for unauthenticated AJAX calls.
        """
        data = {'user_ids': [self.user_with_email.id], 'notification_type': 'email', 'message': 'Test message'}

        resp = self.post(self.url, data=data, authorized=False, ajax=True)
        assert resp.status_code == 404

    @patch('dashboard.services.send_mail_notification')
    @patch('dashboard.services.send_sms')
    def test_mixed_success_and_skip(self, mock_send_sms, mock_send_mail):
        """API should handle mixed scenarios: some sent, some skipped."""
        mock_send_mail.return_value = None
        mock_send_sms.return_value = None

        data = {
            'user_ids': [
                self.user_with_both.id,  # Has both
                self.user_with_email.id,  # Has email only
                self.user_no_contact.id,  # Has neither
            ],
            'notification_type': 'email_and_sms',
            'message': 'Test message',
        }

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        response_data = resp.json()
        assert 'msg' in response_data

        # Should send 2 emails (user_with_both, user_with_email)
        # Should send 1 SMS (user_with_both)
        assert mock_send_mail.call_count == 2
        assert mock_send_sms.call_count == 1

    @patch('dashboard.services.send_mail_notification')
    def test_non_existent_user_ids_handled_gracefully(self, mock_send_mail):
        """API should handle non-existent user IDs without crashing."""
        mock_send_mail.return_value = None

        data = {
            'user_ids': [99999, self.user_with_email.id, 88888],
            'notification_type': 'email',
            'message': 'Test message',
        }

        self.post(self.url, data=data, user=self.manager, ajax=True)

        # Should only send to the one valid user
        assert mock_send_mail.call_count == 1

    @patch('dashboard.services.send_mail_notification')
    def test_special_characters_in_message(self, mock_send_mail):
        """API should handle special characters in message correctly."""
        mock_send_mail.return_value = None

        special_message = "Hello! This message has: <html>, &quot;quotes&quot;, and émojis 🎉"

        data = {'user_ids': [self.user_with_email.id], 'notification_type': 'email', 'message': special_message}

        resp = self.post(self.url, data=data, user=self.manager, ajax=True)

        assert resp.status_code == 200
        assert mock_send_mail.called
        # Verify the message was sent with special characters intact
        call_args = mock_send_mail.call_args
        assert call_args.kwargs['message'] == special_message
