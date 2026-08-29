# base/providers.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseNotificationAdapter(ABC):
    """Base class for all notification provider adapters"""

    def __init__(self, integration):
        """
        Initialize adapter with integration configuration

        Args:
            integration: Integration model instance containing credentials and config
        """
        self.integration = integration
        self.credentials = integration.credentials
        self.configuration = integration.configuration
        self.is_test_mode = integration.is_test_mode

    @abstractmethod
    def send_sms(self, recipient: str, message: str) -> Dict:
        """
        Send SMS to a single recipient

        Args:
            recipient: Phone number in E.164 format
            message: SMS message content

        Returns:
            Dict with keys:
                - success (bool): Whether the send was successful
                - message_id (str): Provider's message ID for tracking
                - status (str): Message status
                - cost (Decimal): Cost in USD (optional)
                - error (str): Error message if failed
                - provider_response (dict): Full provider response
        """
        pass

    @abstractmethod
    def send_email(self, recipient: str, subject: str, body: str, html_body: Optional[str] = None) -> Dict:
        """
        Send email to a single recipient

        Args:
            recipient: Email address
            subject: Email subject
            body: Plain text email body
            html_body: HTML email body (optional)

        Returns:
            Dict with keys:
                - success (bool): Whether the send was successful
                - message_id (str): Provider's message ID for tracking
                - status (str): Message status
                - error (str): Error message if failed
                - provider_response (dict): Full provider response
        """
        pass

    @abstractmethod
    def test_connection(self) -> Dict:
        """
        Test connection to provider

        Returns:
            Dict with keys:
                - success (bool): Whether connection test passed
                - message (str): Success or error message
                - account_info (dict): Account information if available
        """
        pass

    @abstractmethod
    def get_delivery_status(self, message_id: str) -> Dict:
        """
        Get delivery status for a message

        Args:
            message_id: Provider's message ID

        Returns:
            Dict with keys:
                - success (bool): Whether status query was successful
                - status (str): Current message status
                - error (str): Error message if failed
        """
        pass

    def validate_credentials(self) -> bool:
        """
        Validate credentials format

        Returns:
            bool: True if all required credentials are present
        """
        required_fields = self.get_required_credentials()
        return all(field in self.credentials for field in required_fields)

    @abstractmethod
    def get_required_credentials(self) -> List[str]:
        """
        Get list of required credential fields

        Returns:
            List[str]: List of required credential field names
        """
        pass