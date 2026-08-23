# providers/klaviyo.py
from typing import Dict, List, Optional
from integrations.base.providers import BaseNotificationAdapter


class KlaviyoAdapter(BaseNotificationAdapter):
    """Adapter for Klaviyo Email API"""

    def __init__(self, integration):
        super().__init__(integration)
        # TODO: Initialize Klaviyo client when implementing
        # from klaviyo_api import KlaviyoAPI
        # self.client = KlaviyoAPI(self.credentials['api_key'])

    def send_sms(self, recipient: str, message: str) -> Dict:
        """Klaviyo doesn't support SMS"""
        raise NotImplementedError("Klaviyo does not support SMS")

    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> Dict:
        """Send email via Klaviyo - TO BE IMPLEMENTED"""
        raise NotImplementedError("Klaviyo adapter not yet implemented")

    def test_connection(self) -> Dict:
        """Test connection to Klaviyo - TO BE IMPLEMENTED"""
        raise NotImplementedError("Klaviyo adapter not yet implemented")

    def get_delivery_status(self, message_id: str) -> Dict:
        """Get delivery status - TO BE IMPLEMENTED"""
        raise NotImplementedError("Klaviyo adapter not yet implemented")

    def get_required_credentials(self) -> List[str]:
        """Required credentials for Klaviyo"""
        return ['api_key']