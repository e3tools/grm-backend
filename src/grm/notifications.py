import logging

import cryptocode
from django.utils.translation import gettext as _

from authentication.models import Cdata
from grm.constants import (
    EMAIL_CHOICE,
    NOTIFICATION_TYPES,
    PHONE_CHOICE,
    WHATSAPP_CHOICE,
)
from mail_client import send_mail_notification
from sms_client import send_sms

logger = logging.getLogger(__name__)


def send_issue_notification(issue, notification_type, message_template=None):
    """
    Send a notification to the issue contact according to the configured contact_method.

    Args:
        issue: Issue model instance
        notification_type: Notification type ('created', 'status_changed', 'appealed', 'assigned')
        message_template: Message template (optional, a default will be generated if not provided)

    Returns:
        bool: True if notification was sent successfully, False otherwise

    Raises:
        ValueError: If notification_type is not supported
    """
    # Validate notification type
    if notification_type not in NOTIFICATION_TYPES:
        raise ValueError(
            f"Unsupported notification_type: '{notification_type}'. "
            f"Supported types: {', '.join(sorted(NOTIFICATION_TYPES))}"
        )

    # If there's no contact_method, skip notification
    if not issue.contact_method:
        logger.info(f"Issue {issue.id}: No contact method specified, skipping notification")
        return False

    # Get decrypted contact from Cdata
    try:
        cdata = Cdata.objects.filter(key=str(issue.id)).first()
        if not cdata:
            logger.warning(f"Issue {issue.id}: No contact information found in Cdata")
            return False

        contact_info = cryptocode.decrypt(cdata.data, str(issue.id))
        if not contact_info:
            logger.warning(f"Issue {issue.id}: Failed to decrypt contact information")
            return False
    except Exception as e:
        logger.error(f"Issue {issue.id}: Error retrieving contact information: {str(e)}")
        return False

    # Generate message if not provided
    if not message_template:
        message_template = _generate_default_message(issue, notification_type)

    # Send according to contact method
    try:
        if issue.contact_method == EMAIL_CHOICE:
            return _send_email_notification(issue, contact_info, notification_type, message_template)
        elif issue.contact_method in [PHONE_CHOICE, WHATSAPP_CHOICE]:
            return _send_sms_notification(issue, contact_info, notification_type, message_template)
        else:
            logger.warning(f"Issue {issue.id}: Unknown contact method '{issue.contact_method}'")
            return False
    except Exception as e:
        logger.error(f"Issue {issue.id}: Error sending notification: {str(e)}")
        return False


def _send_email_notification(issue, email, notification_type, message):
    """
    Send a notification via email.

    Args:
        issue: Issue model instance
        email: Recipient email address
        notification_type: Type of notification
        message: Message body

    Returns:
        bool: True if sent successfully, False otherwise

    Raises:
        Exception: If email sending fails
    """
    subject = _generate_email_subject(issue, notification_type)

    try:
        send_mail_notification(subject=subject, message=message, recipient=email)
        logger.info(f"Issue {issue.id}: Email notification ({notification_type}) sent successfully to {email}")
        return True
    except Exception as e:
        logger.error(f"Issue {issue.id}: Failed to send email ({notification_type}) to {email}: {str(e)}")
        raise


def _send_sms_notification(issue, phone_number, notification_type, message):
    """
    Send a notification via SMS/WhatsApp.

    Args:
        issue: Issue model instance
        phone_number: Recipient phone number
        notification_type: Type of notification
        message: Message body

    Returns:
        bool: True if sent successfully, False otherwise

    Raises:
        Exception: If SMS sending fails
    """
    # Truncate message to 160 characters for SMS
    sms_message = message[:160]

    # Format phone number
    phone = _format_phone_number(phone_number)

    try:
        send_sms(to=phone, body=sms_message)
        logger.info(f"Issue {issue.id}: SMS notification ({notification_type}) sent successfully to {phone}")
        return True
    except Exception as e:
        logger.error(f"Issue {issue.id}: Failed to send SMS ({notification_type}) to {phone}: {str(e)}")
        raise


def _format_phone_number(phone_number):
    """
    Format a phone number for SMS sending.

    Args:
        phone_number: Phone number string (may contain spaces, special chars, etc)

    Returns:
        str: Formatted phone number with + prefix
    """
    # Remove spaces and special characters
    phone = ''.join(filter(str.isdigit, phone_number))

    # Add + prefix if not present
    if not phone.startswith('+'):
        phone = f"+{phone}"

    return phone


def _generate_email_subject(issue, notification_type):
    """
    Generate email subject based on notification type.

    Args:
        issue: Issue model instance
        notification_type: Type of notification

    Returns:
        str: Formatted email subject
    """
    subjects = {
        'created': _("Issue Created - Tracking Code: {tracking_code}"),
        'status_changed': _("Issue Status Updated - Tracking Code: {tracking_code}"),
        'appealed': _("Issue Appealed - Tracking Code: {tracking_code}"),
        'assigned': _("Issue Assigned - Tracking Code: {tracking_code}"),
    }

    subject_template = subjects.get(notification_type, _("Issue Notification - Tracking Code: {tracking_code}"))
    return subject_template.format(tracking_code=issue.tracking_code)


def _generate_default_message(issue, notification_type):
    """
    Generate a default message based on notification type.

    Args:
        issue: Issue model instance
        notification_type: Type of notification

    Returns:
        str: Formatted message body with issue details

    Examples:
        >>> message = _generate_default_message(issue, 'created')
        >>> 'Tracking Code:' in message
        True
    """
    # Base message templates
    messages = {
        'created': _(
            "Dear citizen,\n\n"
            "Your issue has been successfully created.\n"
            "Tracking Code: {tracking_code}\n"
            "Status: {status}\n\n"
            "Thank you for your report."
        ),
        'status_changed': _(
            "Dear citizen,\n\n"
            "The status of your issue has been updated.\n"
            "Tracking Code: {tracking_code}\n"
            "New Status: {status}\n"
            "{additional_info}\n"
            "Thank you for your patience."
        ),
        'appealed': _(
            "Dear citizen,\n\n"
            "Your appeal has been sent.\n"
            "Tracking Code: {tracking_code}\n"
            "Current Status: {status}\n"
            "Appeal Status: {appeal_status}\n"
            "{additional_info}\n"
            "Thank you for your patience."
        ),
        'assigned': _(
            "Dear citizen,\n\n"
            "Your issue has been assigned to a staff member.\n"
            "Tracking Code: {tracking_code}\n"
            "Status: {status}\n\n"
            "We are working on resolving your issue."
        ),
    }

    message_template = messages.get(
        notification_type,
        _("Dear citizen,\n\n" "Your issue has been updated.\n" "Tracking Code: {tracking_code}\n\n" "Thank you."),
    )

    # Build additional info for status_changed and appealed notifications
    additional_info = ""
    if notification_type == 'status_changed':
        if issue.research_result:
            additional_info = _("Resolution: {research_result}\n").format(research_result=issue.research_result)
        elif issue.reject_reason:
            additional_info = _("Reject Reason: {reject_reason}\n").format(reject_reason=issue.reject_reason)
    elif notification_type == 'appealed':
        additional_info = _("Appeal Reason: {appeal_reason}\n").format(appeal_reason=issue.appeal_reason)

    return message_template.format(
        tracking_code=issue.tracking_code,
        status=issue.status.name if issue.status else _("Unknown"),
        additional_info=additional_info,
    )
