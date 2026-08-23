# providers/africas_talking.py
from typing import Dict, List, Optional
import africastalking
from integrations.base.providers import BaseNotificationAdapter


class AfricasTalkingAdapter(BaseNotificationAdapter):
    """Adapter for Africa's Talking SMS API"""

    def __init__(self, integration):
        super().__init__(integration)

        # Initialize Africa's Talking
        africastalking.initialize(
            username=self.credentials['username'],
            api_key=self.credentials['api_key']
        )
        self.sms = africastalking.SMS

        # Get application data to verify credentials
        self.application = africastalking.Application

        # Get configuration
        self.sender_id = self.configuration.get('sender_id', 'GRM')

    def send_sms(self, recipient: str, message: str) -> Dict:
        """
        Send SMS via Africa's Talking

        Args:
            recipient: Phone number in international format (e.g., +254712345678)
            message: SMS message content

        Returns:
            Dict with success status, message_id, and provider response
        """
        try:
            # Prepare recipients list (Africa's Talking accepts a list)
            recipients = [recipient]

            # Send SMS
            response = self.sms.send(
                message=message,
                recipients=recipients,
                sender_id=self.sender_id
            )

            sms_data = response.get('SMSMessageData', {})
            recipients_data = sms_data.get('Recipients', [])

            if recipients_data and len(recipients_data) > 0:
                recipient_data = recipients_data[0]
                status_code = recipient_data.get('statusCode')

                # Status codes: 100 (Processed), 101 (Sent), 102 (Queued)
                success = status_code in [100, 101, 102]

                # Extract cost (e.g., "KES 0.8000" -> 0.8)
                cost_str = recipient_data.get('cost', '')
                cost = None
                if cost_str:
                    try:
                        cost = float(cost_str.split()[-1])
                    except:
                        pass

                return {
                    'success': success,
                    'message_id': recipient_data.get('messageId', ''),
                    'status': recipient_data.get('status', 'Unknown'),
                    'cost': cost,
                    'provider_response': {
                        'status_code': status_code,
                        'number': recipient_data.get('number'),
                        'cost': cost_str,
                        'message': sms_data.get('Message', '')
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'No recipient data in response',
                    'provider_response': response
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider_response': {}
            }

    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> Dict:
        """Africa's Talking doesn't support email"""
        raise NotImplementedError("Africa's Talking does not support email")

    def test_connection(self) -> Dict:
        """
        Test connection to Africa's Talking by checking application status

        Returns:
            Dict with success status and message
        """
        try:
            # Try to fetch user data (this will fail if credentials are invalid)
            user_data = self.application.fetch_application_data()

            if user_data:
                return {
                    'success': True,
                    'message': 'Connection successful',
                    'account_info': {
                        'username': self.credentials.get('username'),
                        'balance': user_data.get('UserData', {}).get('balance', 'N/A')
                    }
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to fetch application data',
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

        Note: Africa's Talking provides delivery status via callbacks.
        Direct query is not available in their standard API.

        Args:
            message_id: Africa's Talking message ID

        Returns:
            Dict with status information
        """
        return {
            'success': False,
            'message': 'Africa\'s Talking delivery status is available via callbacks only',
            'status': 'unknown'
        }

    def get_required_credentials(self) -> List[str]:
        """
        Get list of required credential fields

        Returns:
            List of required credential field names
        """
        return ['username', 'api_key']