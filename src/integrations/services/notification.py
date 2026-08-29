# services/notification.py
from datetime import timedelta
from typing import Optional, List
from django.utils import timezone
from integrations.models import NotificationLog, NotificationRule
from integrations.services.sms import SMSService
from integrations.services.email import EmailService


class NotificationService:
    """
    Unified notification service that orchestrates SMS and email notifications
    and handles automated rule-based notifications
    """

    @staticmethod
    def send_sms(
        recipient: str,
        message: str,
        integration=None,
        issue=None,
        user=None,
        template=None
    ) -> NotificationLog:
        """
        Send SMS notification

        Delegates to SMSService.send_sms()
        """
        return SMSService.send_sms(
            recipient=recipient,
            message=message,
            integration=integration,
            issue=issue,
            user=user,
            template=template
        )

    @staticmethod
    def send_email(
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        integration=None,
        issue=None,
        user=None,
        template=None
    ) -> NotificationLog:
        """
        Send email notification

        Delegates to EmailService.send_email()
        """
        return EmailService.send_email(
            recipient=recipient,
            subject=subject,
            body=body,
            html_body=html_body,
            integration=integration,
            issue=issue,
            user=user,
            template=template
        )

    @staticmethod
    def trigger_rules(event: str, context: dict) -> List[NotificationLog]:
        """
        Trigger notification rules based on event

        Args:
            event: Event name (e.g., 'issue_created', 'issue_assigned')
            context: Context data with variables for template rendering
                     Should include 'issue' and 'user' if available

        Returns:
            List of NotificationLog instances created

        Example:
            context = {
                'issue': issue_instance,
                'issue_id': issue.id,
                'issue_title': issue.title,
                'citizen_name': issue.citizen.name,
                'category': issue.category.name
            }
            logs = NotificationService.trigger_rules('issue_created', context)
        """

        # Get active rules for this event, ordered by priority
        rules = NotificationRule.objects.filter(
            trigger_event=event,
            is_active=True
        ).select_related('integration', 'template').order_by('-priority')

        logs = []

        for rule in rules:
            # Check trigger conditions
            if not NotificationService._check_conditions(rule.trigger_conditions, context):
                continue

            # Check rate limits
            if not NotificationService._check_rate_limits(rule):
                continue

            # Get recipients based on recipient_type
            recipients = NotificationService._get_recipients(rule, context)

            if not recipients:
                continue

            # Render template if available
            if rule.template:
                rendered = rule.template.render(context)
                if rule.integration.provider.provider_type == 'email':
                    subject, body = rendered
                else:
                    subject = None
                    body = rendered
            else:
                # Use context values if no template
                subject = context.get('subject', '')
                body = context.get('body', '')

            # Send to each recipient
            for recipient in recipients:
                try:
                    if rule.integration.provider.provider_type == 'sms':
                        log = NotificationService.send_sms(
                            recipient=recipient,
                            message=body,
                            integration=rule.integration,
                            issue=context.get('issue'),
                            user=context.get('user'),
                            template=rule.template
                        )
                    else:  # email
                        log = NotificationService.send_email(
                            recipient=recipient,
                            subject=subject,
                            body=body,
                            integration=rule.integration,
                            issue=context.get('issue'),
                            user=context.get('user'),
                            template=rule.template
                        )

                    logs.append(log)

                except Exception as e:
                    # Log error but continue with other recipients
                    print(f"Error sending notification to {recipient}: {e}")

            # Update rule stats
            rule.times_triggered += 1
            rule.last_triggered_at = timezone.now()
            rule.save(update_fields=['times_triggered', 'last_triggered_at'])

        return logs

    @staticmethod
    def _check_conditions(conditions: dict, context: dict) -> bool:
        """
        Check if trigger conditions are met

        Args:
            conditions: Rule trigger conditions
            context: Context data

        Returns:
            True if all conditions are met, False otherwise
        """
        if not conditions:
            return True

        for key, value in conditions.items():
            # Support nested keys with dot notation (e.g., 'issue.category')
            context_value = context.get(key)

            # If key has dot notation, traverse the context
            if '.' in key:
                parts = key.split('.')
                context_value = context
                for part in parts:
                    if hasattr(context_value, part):
                        context_value = getattr(context_value, part)
                    elif isinstance(context_value, dict):
                        context_value = context_value.get(part)
                    else:
                        context_value = None
                        break

            # Check if condition matches
            if context_value != value:
                return False

        return True

    @staticmethod
    def _check_rate_limits(rule: NotificationRule) -> bool:
        """
        Check if rule has exceeded rate limits

        Args:
            rule: NotificationRule instance

        Returns:
            True if within rate limits, False if exceeded
        """
        now = timezone.now()

        # Check hourly rate limit
        if rule.max_per_hour:
            hour_ago = now - timedelta(hours=1)
            count = NotificationLog.objects.filter(
                integration=rule.integration,
                template=rule.template,
                created_at__gte=hour_ago
            ).count()

            if count >= rule.max_per_hour:
                return False

        # Check daily rate limit
        if rule.max_per_day:
            day_ago = now - timedelta(days=1)
            count = NotificationLog.objects.filter(
                integration=rule.integration,
                template=rule.template,
                created_at__gte=day_ago
            ).count()

            if count >= rule.max_per_day:
                return False

        return True

    @staticmethod
    def _get_recipients(rule: NotificationRule, context: dict) -> List[str]:
        """
        Get recipients based on rule recipient_type

        Args:
            rule: NotificationRule instance
            context: Context data

        Returns:
            List of recipient phone numbers or email addresses
        """
        recipients = []
        provider_type = rule.integration.provider.provider_type

        if rule.recipient_type == 'citizen':
            issue = context.get('issue')
            if issue and hasattr(issue, 'citizen') and issue.citizen:
                if provider_type == 'sms':
                    if hasattr(issue.citizen, 'phone_number'):
                        recipients.append(issue.citizen.phone_number)
                else:  # email
                    if hasattr(issue.citizen, 'email'):
                        recipients.append(issue.citizen.email)

        elif rule.recipient_type == 'assigned_worker':
            issue = context.get('issue')
            if issue and hasattr(issue, 'assigned_to') and issue.assigned_to:
                if provider_type == 'sms':
                    if hasattr(issue.assigned_to, 'phone_number'):
                        recipients.append(issue.assigned_to.phone_number)
                else:  # email
                    if hasattr(issue.assigned_to, 'email'):
                        recipients.append(issue.assigned_to.email)

        elif rule.recipient_type == 'facilitator':
            issue = context.get('issue')
            if issue and hasattr(issue, 'facilitator') and issue.facilitator:
                if provider_type == 'sms':
                    if hasattr(issue.facilitator, 'phone_number'):
                        recipients.append(issue.facilitator.phone_number)
                else:  # email
                    if hasattr(issue.facilitator, 'email'):
                        recipients.append(issue.facilitator.email)

        elif rule.recipient_type == 'regional_managers':
            # Get regional managers from context if provided
            managers = context.get('regional_managers', [])
            if provider_type == 'sms':
                recipients = [m.phone_number for m in managers if hasattr(m, 'phone_number')]
            else:  # email
                recipients = [m.email for m in managers if hasattr(m, 'email')]

        elif rule.recipient_type == 'custom':
            # Use custom recipients list from rule
            recipients = rule.custom_recipients or []

        return recipients