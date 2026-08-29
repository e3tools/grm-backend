import logging

from django.db.models import Q
from django.utils.translation import gettext as _

from authentication.models import User
from mail_client import send_mail_notification
from sms_client import send_sms

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service to handle bulk email and SMS notifications to inactive users.
    """

    SMS_MAX_LENGTH = 160

    @staticmethod
    def send_bulk_notifications(user_ids, notification_type, message):
        """
        Send bulk notifications to specified users.

        Args:
            user_ids (list): List of user IDs to notify
            notification_type (str): 'email', 'sms' or 'email_and_sms'
            message (str): Message content to send

        Returns:
            dict: Results summary with success/failure counts
        """
        results = {
            'total': len(user_ids),
            'success_email': 0,
            'success_sms': 0,
            'failed': 0,
            'skipped': 0,
            'errors': [],
        }

        if not user_ids:
            return results

        users = User.objects.filter(id__in=user_ids).only('id', 'first_name', 'last_name', 'email', 'phone_number')

        for user in users:
            try:
                success_email = False
                success_sms = False

                if notification_type in ['email', 'email_and_sms']:
                    success_email = NotificationService._send_email(user, message)
                    if success_email:
                        results['success_email'] += 1

                if notification_type in ['sms', 'email_and_sms']:
                    success_sms = NotificationService._send_sms(user, message)
                    if success_sms:
                        results['success_sms'] += 1

                if not success_email and not success_sms:
                    results['skipped'] += 1

            except Exception as e:
                results['failed'] += 1
                error_msg = f"{user.name}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(f"Failed to send {notification_type} to user {user.id}: {str(e)}")

        return results

    @staticmethod
    def _send_email(user, message):
        """
        Send email to a single user.

        Returns:
            bool: True if sent, False if skipped (no email)

        Raises:
            Exception: If email sending fails
        """
        if not user.email:
            logger.warning(f"User {user.id} has no email address")
            return False

        subject = _("Activity Reminder - GRM System")

        send_mail_notification(subject=subject, message=message, recipient=user.email)

        logger.info(f"Email sent successfully to {user.email}")
        return True

    @staticmethod
    def _send_sms(user, message):
        """
        Send SMS to a single user.

        Returns:
            bool: True if sent, False if skipped (no phone)

        Raises:
            Exception: If SMS sending fails
        """
        if not user.phone_number:
            logger.warning(f"User {user.id} has no phone number")
            return False

        # Format phone number
        phone = NotificationService._format_phone_number(user.phone_number)

        sms_message = message[: NotificationService.SMS_MAX_LENGTH]

        send_sms(to=phone, body=sms_message)

        logger.info(f"SMS sent successfully to {phone}")
        return True

    @staticmethod
    def _format_phone_number(phone_number):
        """
        Format phone number for SMS sending.

        Args:
            phone_number (str): Raw phone number from database

        Returns:
            str: Formatted phone number with + prefix
        """
        # Remove spaces and special characters
        phone = ''.join(filter(str.isdigit, phone_number))

        # Add + prefix if not present
        if not phone.startswith('+'):
            phone = f"+{phone}"

        return phone

    @staticmethod
    def get_users_info(user_ids):
        """
        Get user information for display in modal.

        Only returns users that have either a Facilitator or GovernmentWorker relation.

        Args:
            user_ids (list): List of user IDs

        Returns:
            list: List of dicts with user info ordered by name
        """
        if not user_ids:
            return []

        users = (
            User.objects.filter(
                Q(facilitator__isnull=False) | Q(governmentworker__isnull=False),
                id__in=user_ids,
            )
            .only('id', 'first_name', 'last_name', 'email', 'phone_number')
            .order_by('first_name', 'last_name')
            .distinct()
        )

        return [
            {
                'id': user.id,
                'name': user.name,
                'email': user.email or _('No email'),
                'phone': user.phone_number or _('No phone'),
                'has_email': bool(user.email),
                'has_phone': bool(user.phone_number),
            }
            for user in users
        ]
