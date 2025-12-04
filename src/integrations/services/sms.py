# services/sms.py
from typing import Optional
from django.utils import timezone
from integrations.models import Integration, NotificationLog
from integrations.base import get_adapter


class SMSService:
    """Service for sending SMS notifications"""

    @staticmethod
    def send_sms(
        recipient: str,
        message: str,
        integration: Optional[Integration] = None,
        issue=None,
        user=None,
        template=None
    ) -> NotificationLog:
        """
        Send SMS notification

        Args:
            recipient: Phone number in E.164 format (e.g., +1234567890)
            message: SMS message content
            integration: Integration to use (defaults to active SMS integration)
            issue: Related Issue object (optional)
            user: Related User object (optional)
            template: NotificationTemplate used (optional)

        Returns:
            NotificationLog instance with send status

        Raises:
            ValueError: If no active SMS integration is found
        """

        # Get integration (use default if not specified)
        if not integration:
            integration = Integration.objects.filter(
                provider__provider_type='sms',
                is_default=True,
                status='active'
            ).first()

            if not integration:
                raise ValueError("No active SMS integration found")

        # Validate integration is for SMS
        if integration.provider.provider_type != 'sms':
            raise ValueError(f"Integration {integration.name} is not an SMS provider")

        # Create log entry
        log = NotificationLog.objects.create(
            integration=integration,
            template=template,
            recipient=recipient,
            issue=issue,
            user=user,
            body=message,
            status='pending'
        )

        try:
            # Get adapter and send
            adapter = get_adapter(integration)
            result = adapter.send_sms(recipient, message)

            # Update log based on result
            if result['success']:
                log.status = 'sent'
                log.sent_at = timezone.now()
                log.provider_message_id = result.get('message_id', '')
                log.provider_response = result.get('provider_response', {})
                log.cost = result.get('cost')

                # Update integration stats
                integration.total_sent += 1
                integration.last_used_at = timezone.now()
                integration.save(update_fields=['total_sent', 'last_used_at'])
            else:
                log.status = 'failed'
                log.failed_at = timezone.now()
                log.error_message = result.get('error', 'Unknown error')
                log.provider_response = result.get('provider_response', {})

                # Update integration stats
                integration.total_failed += 1
                integration.save(update_fields=['total_failed'])

            log.save()
            return log

        except Exception as e:
            # Handle unexpected errors
            log.status = 'failed'
            log.failed_at = timezone.now()
            log.error_message = str(e)
            log.save()

            # Update integration stats
            integration.total_failed += 1
            integration.save(update_fields=['total_failed'])

            raise

    @staticmethod
    def get_delivery_status(message_id: str, integration: Integration) -> dict:
        """
        Get delivery status for a sent SMS

        Args:
            message_id: Provider's message ID
            integration: Integration used to send the message

        Returns:
            Dict with delivery status information
        """
        adapter = get_adapter(integration)
        return adapter.get_delivery_status(message_id)