# providers/africas_talking.py
from typing import Dict, List, Optional
from integrations.base.providers import BaseNotificationAdapter


class AfricasTalkingAdapter(BaseNotificationAdapter):
    """Adapter for Africa's Talking SMS API"""

    def __init__(self, integration):
        super().__init__(integration)
        # TODO: Initialize Africa's Talking client when implementing
        # import africastalking
        # africastalking.initialize(
        #     username=self.credentials['username'],
        #     api_key=self.credentials['api_key']
        # )
        # self.sms = africastalking.SMS

    def send_sms(self, recipient: str, message: str) -> Dict:
        """Send SMS via Africa's Talking - TO BE IMPLEMENTED"""
        raise NotImplementedError("Africa's Talking adapter not yet implemented")

    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> Dict:
        """Africa's Talking doesn't support email"""
        raise NotImplementedError("Africa's Talking does not support email")

    def test_connection(self) -> Dict:
        """Test connection to Africa's Talking - TO BE IMPLEMENTED"""
        raise NotImplementedError("Africa's Talking adapter not yet implemented")

    def get_delivery_status(self, message_id: str) -> Dict:
        """Get delivery status - TO BE IMPLEMENTED"""
        raise NotImplementedError("Africa's Talking adapter not yet implemented")

    def get_required_credentials(self) -> List[str]:
        """Required credentials for Africa's Talking"""
        return ['username', 'api_key']