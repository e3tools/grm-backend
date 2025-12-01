# providers/sendgrid.py
from typing import Dict, List, Optional
from integrations.base.providers import BaseNotificationAdapter


class SendGridAdapter(BaseNotificationAdapter):
    """Adapter for SendGrid Email API"""

    def __init__(self, integration):
        super().__init__(integration)
        # TODO: Initialize SendGrid client when implementing
        # from sendgrid import SendGridAPIClient
        # self.client = SendGridAPIClient(self.credentials['api_key'])

    def send_sms(self, recipient: str, message: str) -> Dict:
        """SendGrid doesn't support SMS"""
        raise NotImplementedError("SendGrid does not support SMS")

    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> Dict:
        """Send email via SendGrid - TO BE IMPLEMENTED"""
        raise NotImplementedError("SendGrid adapter not yet implemented")

    def test_connection(self) -> Dict:
        """Test connection to SendGrid - TO BE IMPLEMENTED"""
        raise NotImplementedError("SendGrid adapter not yet implemented")

    def get_delivery_status(self, message_id: str) -> Dict:
        """Get delivery status - TO BE IMPLEMENTED"""
        raise NotImplementedError("SendGrid adapter not yet implemented")

    def get_required_credentials(self) -> List[str]:
        """Required credentials for SendGrid"""
        return ['api_key']