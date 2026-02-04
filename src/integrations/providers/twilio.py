# providers/twilio.py
from typing import Dict, List, Optional
from twilio.rest import Client
from integrations.base.providers import BaseNotificationAdapter


class TwilioAdapter(BaseNotificationAdapter):
    """Adapter for Twilio SMS API"""

    def __init__(self, integration):
        super().__init__(integration)

        # Initialize Twilio client
        self.client = Client(
            self.credentials['account_sid'],
            self.credentials['auth_token']
        )

        # Get configuration
        self.from_number = self.configuration.get('from_number')
        self.callback_url = self.configuration.get('callback_url')

    def send_sms(self, recipient: str, message: str) -> Dict:
        """
        Send SMS via Twilio

        Args:
            recipient: Phone number in E.164 format (e.g., +1234567890)
            message: SMS message content

        Returns:
            Dict with success status, message_id, and provider response
        """
        try:
            # Prepare message parameters
            message_params = {
                'body': message,
                'from_': self.from_number,
                'to': recipient
            }

            # Add callback URL if configured
            if self.callback_url:
                message_params['status_callback'] = self.callback_url

            # Send message
            message_obj = self.client.messages.create(**message_params)

            return {
                'success': True,
                'message_id': message_obj.sid,
                'status': message_obj.status,
                'cost': float(message_obj.price) if message_obj.price else None,
                'provider_response': {
                    'sid': message_obj.sid,
                    'status': message_obj.status,
                    'price': message_obj.price,
                    'price_unit': message_obj.price_unit,
                    'direction': message_obj.direction,
                    'to': message_obj.to,
                    'from': message_obj.from_
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider_response': {}
            }

    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> Dict:
        """Twilio SMS doesn't support email"""
        raise NotImplementedError("Twilio SMS does not support email")

    def test_connection(self) -> Dict:
        """
        Test connection by fetching account info

        Returns:
            Dict with success status and account information
        """
        try:
            # Fetch account details to verify credentials
            account = self.client.api.accounts(self.credentials['account_sid']).fetch()

            return {
                'success': True,
                'message': 'Connection successful',
                'account_info': {
                    'sid': account.sid,
                    'name': account.friendly_name,
                    'status': account.status,
                    'type': account.type
                }
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

        Args:
            message_id: Twilio message SID

        Returns:
            Dict with current message status
        """
        try:
            # Fetch message by SID
            message = self.client.messages(message_id).fetch()

            return {
                'success': True,
                'status': message.status,
                'error_code': message.error_code,
                'error_message': message.error_message,
                'date_sent': message.date_sent.isoformat() if message.date_sent else None,
                'date_updated': message.date_updated.isoformat() if message.date_updated else None
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'status': 'unknown'
            }

    def get_required_credentials(self) -> List[str]:
        """
        Get list of required credential fields

        Returns:
            List of required credential field names
        """
        return ['account_sid', 'auth_token']