# providers/sendgrid.py
from typing import Dict, List, Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Content
from integrations.base.providers import BaseNotificationAdapter


class SendGridAdapter(BaseNotificationAdapter):
    """Adapter for SendGrid Email API"""

    def __init__(self, integration):
        super().__init__(integration)

        # Initialize SendGrid client
        self.client = SendGridAPIClient(self.credentials['api_key'])

        # Set EU data residency if configured
        # NOTE: Only enable this if your SendGrid account is set up for EU region
        # self.client.set_sendgrid_data_residency("eu")

        # Get configuration
        self.from_email = self.configuration.get('from_email')
        self.from_name = self.configuration.get('from_name', 'GRM Platform')
        self.reply_to = self.configuration.get('reply_to')
        self.track_opens = self.configuration.get('track_opens', True)
        self.track_clicks = self.configuration.get('track_clicks', True)

    def send_sms(self, recipient: str, message: str) -> Dict:
        """SendGrid doesn't support SMS"""
        raise NotImplementedError("SendGrid does not support SMS")

    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> Dict:
        """
        Send email via SendGrid

        Args:
            recipient: Email address
            subject: Email subject line
            body: Plain text email body
            html_body: HTML email body (optional)

        Returns:
            Dict with success status, message_id, and provider response
        """
        try:
            # Build email data dictionary
            from_name = self.from_name if self.from_name else 'GRM Platform'

            mail_data = {
                'personalizations': [
                    {
                        'to': [{'email': recipient}],
                        'subject': subject
                    }
                ],
                'from': {
                    'email': self.from_email,
                    'name': from_name
                },
                'content': [
                    {
                        'type': 'text/plain',
                        'value': body
                    }
                ]
            }

            # Add HTML content if provided
            if html_body:
                mail_data['content'].append({
                    'type': 'text/html',
                    'value': html_body
                })

            # Add reply-to if configured
            if self.reply_to:
                mail_data['reply_to'] = {
                    'email': self.reply_to
                }

            # Add tracking settings
            mail_data['tracking_settings'] = {
                'click_tracking': {
                    'enable': self.track_clicks,
                    'enable_text': False
                },
                'open_tracking': {
                    'enable': self.track_opens
                }
            }

            # Send using the API client directly
            response = self.client.client.mail.send.post(request_body=mail_data)

            # Convert response body from bytes to string if needed
            response_body = ''
            if hasattr(response, 'body') and response.body:
                if isinstance(response.body, bytes):
                    response_body = response.body.decode('utf-8')
                else:
                    response_body = str(response.body)

            return {
                'success': response.status_code in [200, 202],
                'message_id': response.headers.get('X-Message-Id', ''),
                'status': 'sent' if response.status_code in [200, 202] else 'failed',
                'provider_response': {
                    'status_code': response.status_code,
                    'body': response_body,
                    'headers': dict(response.headers)
                }
            }

        except Exception as e:
            print(f'ERROR: {str(e)}')
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'provider_response': {}
            }

    def test_connection(self) -> Dict:
        """
        Test connection to SendGrid by verifying API key

        Returns:
            Dict with success status and message
        """
        try:
            # Try to get API key scopes to verify the key is valid
            response = self.client.client.api_keys._(self.credentials['api_key_id']).get()

            if response.status_code == 200:
                return {
                    'success': True,
                    'message': 'Connection successful',
                    'account_info': {
                        'api_key_valid': True,
                        'status_code': response.status_code
                    }
                }
            else:
                return {
                    'success': False,
                    'message': f'Connection failed with status code: {response.status_code}',
                    'account_info': {}
                }

        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}',
                'account_info': {}
            }

    def get_delivery_status(self, message_id: str) -> Dict:
        """
        Get delivery status for a message

        Note: SendGrid provides delivery status via Event Webhook, not direct API query.
        This method returns a message indicating webhook-based status updates.

        Args:
            message_id: SendGrid message ID

        Returns:
            Dict with status information
        """
        return {
            'success': False,
            'message': 'SendGrid delivery status is available via Event Webhook only',
            'status': 'unknown'
        }

    def get_required_credentials(self) -> List[str]:
        """
        Get list of required credential fields

        Returns:
            List of required credential field names
        """
        return ['api_key']