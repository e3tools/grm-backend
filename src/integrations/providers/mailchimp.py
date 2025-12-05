# providers/mailchimp.py
from typing import Dict, List, Optional
import mailchimp_transactional as MailchimpTransactional
from mailchimp_transactional.api_client import ApiClientError
from integrations.base.providers import BaseNotificationAdapter


class MailchimpAdapter(BaseNotificationAdapter):
    """Adapter for Mailchimp Transactional Email API (formerly Mandrill)"""

    def __init__(self, integration):
        super().__init__(integration)

        # Initialize Mailchimp Transactional client
        self.client = MailchimpTransactional.Client(self.credentials['api_key'])

        # Get configuration
        self.from_email = self.configuration.get('from_email')
        self.from_name = self.configuration.get('from_name', 'GRM Platform')
        self.reply_to = self.configuration.get('reply_to')
        self.track_opens = self.configuration.get('track_opens', True)
        self.track_clicks = self.configuration.get('track_clicks', True)

    def send_sms(self, recipient: str, message: str) -> Dict:
        """Mailchimp doesn't support SMS"""
        raise NotImplementedError("Mailchimp does not support SMS")

    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> Dict:
        """
        Send email via Mailchimp Transactional API

        Args:
            recipient: Email address
            subject: Email subject line
            body: Plain text email body
            html_body: HTML email body (optional)

        Returns:
            Dict with success status, message_id, and provider response
        """
        try:
            # Prepare message data
            message = {
                'from_email': self.from_email,
                'from_name': self.from_name,
                'subject': subject,
                'text': body,
                'to': [
                    {
                        'email': recipient,
                        'type': 'to'
                    }
                ],
                'track_opens': self.track_opens,
                'track_clicks': self.track_clicks,
            }

            # Add HTML content if provided
            if html_body:
                message['html'] = html_body

            # Add reply-to if configured
            if self.reply_to:
                message['headers'] = {
                    'Reply-To': self.reply_to
                }

            # Send the message
            response = self.client.messages.send({
                'message': message
            })

            # Mailchimp returns a list with one item for each recipient
            if response and len(response) > 0:
                result = response[0]
                status = result.get('status', 'unknown')

                # Status can be: sent, queued, scheduled, rejected, invalid
                success = status in ['sent', 'queued', 'scheduled']

                return {
                    'success': success,
                    'message_id': result.get('_id', ''),
                    'status': status,
                    'provider_response': {
                        'result': result,
                        'email': result.get('email'),
                        'status': status,
                        'reject_reason': result.get('reject_reason')
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'No response from Mailchimp',
                    'provider_response': {}
                }

        except ApiClientError as e:
            return {
                'success': False,
                'error': str(e),
                'provider_response': {
                    'error': e.text if hasattr(e, 'text') else str(e)
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider_response': {}
            }

    def test_connection(self) -> Dict:
        """
        Test connection to Mailchimp by pinging the API

        Returns:
            Dict with success status and message
        """
        try:
            # Ping the API to verify connection
            response = self.client.users.ping()

            if response and response == 'PONG!':
                return {
                    'success': True,
                    'message': 'Connection successful',
                    'account_info': {
                        'ping': response
                    }
                }
            else:
                return {
                    'success': False,
                    'message': 'Connection failed: Invalid response',
                    'account_info': {}
                }

        except ApiClientError as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}',
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

        Args:
            message_id: Mailchimp message ID

        Returns:
            Dict with status information
        """
        try:
            # Query message info
            response = self.client.messages.info({'id': message_id})

            if response:
                return {
                    'success': True,
                    'status': response.get('state', 'unknown'),
                    'opens': response.get('opens', 0),
                    'clicks': response.get('clicks', 0),
                    'sent_at': response.get('ts'),
                    'opens_detail': response.get('opens_detail', []),
                    'clicks_detail': response.get('clicks_detail', [])
                }
            else:
                return {
                    'success': False,
                    'error': 'Message not found',
                    'status': 'unknown'
                }

        except ApiClientError as e:
            return {
                'success': False,
                'error': str(e),
                'status': 'unknown'
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
        return ['api_key']