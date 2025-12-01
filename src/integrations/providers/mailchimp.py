# providers/mailchimp.py
from typing import Dict, List, Optional
from integrations.base.providers import BaseNotificationAdapter


class MailchimpAdapter(BaseNotificationAdapter):
    """Adapter for Mailchimp Email API"""

    def __init__(self, integration):
        super().__init__(integration)
        # TODO: Initialize Mailchimp client when implementing
        # import mailchimp_marketing as MailchimpMarketing
        # self.client = MailchimpMarketing.Client()
        # self.client.set_config({
        #     "api_key": self.credentials['api_key'],
        #     "server": self.credentials['server_prefix']
        # })

    def send_sms(self, recipient: str, message: str) -> Dict:
        """Mailchimp doesn't support SMS"""
        raise NotImplementedError("Mailchimp does not support SMS")

    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> Dict:
        """Send email via Mailchimp - TO BE IMPLEMENTED"""
        raise NotImplementedError("Mailchimp adapter not yet implemented")

    def test_connection(self) -> Dict:
        """Test connection to Mailchimp - TO BE IMPLEMENTED"""
        raise NotImplementedError("Mailchimp adapter not yet implemented")

    def get_delivery_status(self, message_id: str) -> Dict:
        """Get delivery status - TO BE IMPLEMENTED"""
        raise NotImplementedError("Mailchimp adapter not yet implemented")

    def get_required_credentials(self) -> List[str]:
        """Required credentials for Mailchimp"""
        return ['api_key', 'server_prefix']