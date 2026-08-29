import uuid
import re
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class NotificationProvider(models.Model):
    """
    Represents a notification service provider with its capabilities and rate limits.
    """
    PROVIDER_TYPE_CHOICES = [
        ('sms', 'SMS'),
        ('email', 'Email'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Provider identifier (africas_talking, twilio, sendgrid, etc.)"
    )
    display_name = models.CharField(max_length=200, help_text="Human-readable name")
    provider_type = models.CharField(max_length=10, choices=PROVIDER_TYPE_CHOICES)
    supports_templates = models.BooleanField(
        default=False,
        help_text="Whether provider has native template support"
    )
    supports_tracking = models.BooleanField(
        default=False,
        help_text="Whether provider supports open/click tracking"
    )
    max_recipients_per_request = models.IntegerField(
        default=1,
        help_text="Maximum recipients per request"
    )
    rate_limit_per_second = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum requests per second"
    )
    rate_limit_per_minute = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum requests per minute"
    )
    rate_limit_per_hour = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum requests per hour"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_name']
        verbose_name = "Notification Provider"
        verbose_name_plural = "Notification Providers"

    def __str__(self):
        return f"{self.display_name} ({self.provider_type.upper()})"

    def clean(self):
        """Validate provider data"""
        if not self.is_active:
            # Check if there are active integrations using this provider
            if hasattr(self, 'integrations') and self.integrations.filter(status='active').exists():
                raise ValidationError(
                    "Cannot deactivate provider with active integrations"
                )


class Integration(models.Model):
    """
    Represents a configured instance of a provider with credentials and settings.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('error', 'Error'),
    ]

    TEST_STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        NotificationProvider,
        on_delete=models.PROTECT,
        related_name='integrations'
    )
    name = models.CharField(max_length=200, help_text="Friendly name for this integration")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    credentials = models.JSONField(
        help_text="Encrypted API keys, tokens, etc.",
        default=dict
    )
    configuration = models.JSONField(
        help_text="Provider-specific settings (sender ID, from email)",
        default=dict
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Use as default for this provider type"
    )
    is_test_mode = models.BooleanField(
        default=True,
        help_text="Run in sandbox/test mode"
    )

    # Statistics
    total_sent = models.IntegerField(default=0)
    total_delivered = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)

    # Testing
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(
        max_length=20,
        choices=TEST_STATUS_CHOICES,
        null=True,
        blank=True
    )
    last_test_message = models.TextField(blank=True)

    # Usage tracking
    last_used_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Integration"
        verbose_name_plural = "Integrations"

    def __str__(self):
        return f"{self.name} ({self.provider.display_name})"

    @property
    def success_rate(self):
        """Calculate delivery success rate"""
        if self.total_sent == 0:
            return 0
        return round((self.total_delivered / self.total_sent) * 100, 2)

    @property
    def is_healthy(self):
        """Check if integration is healthy based on recent tests"""
        if self.status != 'active':
            return False
        if not self.last_test_at:
            return False
        if self.last_test_status != 'success':
            return False
        return (timezone.now() - self.last_test_at).days < 1

    def clean(self):
        """Validate integration data"""
        # Only one integration per provider can be default
        if self.is_default:
            existing_default = Integration.objects.filter(
                provider__provider_type=self.provider.provider_type,
                is_default=True
            ).exclude(pk=self.pk)

            if existing_default.exists():
                raise ValidationError(
                    f"Another integration is already set as default for {self.provider.provider_type}"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class NotificationTemplate(models.Model):
    """
    Reusable templates for SMS and Email notifications with variable substitution.
    """
    TEMPLATE_TYPE_CHOICES = [
        ('sms', 'SMS'),
        ('email', 'Email'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Template name")
    template_type = models.CharField(max_length=10, choices=TEMPLATE_TYPE_CHOICES)
    trigger_event = models.CharField(
        max_length=100,
        help_text="Event that triggers this template",
        db_index=True
    )
    subject = models.CharField(
        max_length=500,
        blank=True,
        help_text="Email subject (not used for SMS)"
    )
    body = models.TextField(help_text="Template body with {{variable}} placeholders")
    available_variables = models.JSONField(
        default=list,
        help_text="List of available variables"
    )
    is_system_template = models.BooleanField(
        default=False,
        help_text="System templates cannot be deleted"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"
        indexes = [
            models.Index(fields=['trigger_event', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.template_type.upper()})"

    def render(self, context):
        """
        Render template with provided context

        Args:
            context (dict): Variables to substitute in the template

        Returns:
            str or tuple: Rendered body for SMS, or (subject, body) tuple for Email
        """
        rendered_body = self.body
        for key, value in context.items():
            pattern = r'\{\{\s*' + re.escape(key) + r'\s*\}\}'
            rendered_body = re.sub(pattern, str(value), rendered_body)

        if self.template_type == 'email':
            rendered_subject = self.subject
            for key, value in context.items():
                pattern = r'\{\{\s*' + re.escape(key) + r'\s*\}\}'
                rendered_subject = re.sub(pattern, str(value), rendered_subject)
            return rendered_subject, rendered_body

        return rendered_body

    def clean(self):
        """Validate template data"""
        if self.template_type == 'email' and not self.subject:
            raise ValidationError("Email templates must have a subject")

        # Validate that all variables in body are documented
        pattern = r'\{\{\s*(\w+)\s*\}\}'
        body_variables = set(re.findall(pattern, self.body))
        if self.template_type == 'email':
            subject_variables = set(re.findall(pattern, self.subject))
            body_variables.update(subject_variables)

        documented_variables = set(self.available_variables)
        undocumented = body_variables - documented_variables

        if undocumented:
            raise ValidationError(
                f"Variables used but not documented: {', '.join(undocumented)}"
            )


class NotificationLog(models.Model):
    """
    Comprehensive log of all sent notifications for tracking, debugging, and analytics.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration,
        on_delete=models.PROTECT,
        related_name='logs'
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )

    # Recipient information
    recipient = models.CharField(
        max_length=255,
        help_text="Phone number or email address",
        db_index=True
    )
    recipient_name = models.CharField(max_length=200, blank=True)

    # Related objects
    issue = models.ForeignKey(
        'issues.Issue',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notification_logs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notification_logs'
    )

    # Content
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField()

    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    # Provider information
    provider_message_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Provider's message ID for tracking"
    )
    provider_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Full provider response"
    )
    error_message = models.TextField(blank=True)

    # Cost tracking
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Cost in USD"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['recipient']),
            models.Index(fields=['integration', 'status']),
            models.Index(fields=['issue']),
            models.Index(fields=['provider_message_id']),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.status} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class NotificationRule(models.Model):
    """
    Automated notification rules that trigger based on events.
    """
    RECIPIENT_TYPE_CHOICES = [
        ('citizen', 'Citizen'),
        ('assigned_worker', 'Assigned Worker'),
        ('facilitator', 'Facilitator'),
        ('regional_managers', 'Regional Managers'),
        ('custom', 'Custom Recipients'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Rule name")
    trigger_event = models.CharField(
        max_length=100,
        help_text="Event that triggers this rule",
        db_index=True
    )
    trigger_conditions = models.JSONField(
        default=dict,
        help_text="Additional conditions (category, region, etc.)"
    )
    integration = models.ForeignKey(
        Integration,
        on_delete=models.PROTECT,
        related_name='rules'
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.PROTECT,
        related_name='rules'
    )
    recipient_type = models.CharField(
        max_length=50,
        choices=RECIPIENT_TYPE_CHOICES,
        help_text="Who receives the notification"
    )
    custom_recipients = models.JSONField(
        default=list,
        blank=True,
        help_text="List of custom recipients"
    )
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=10,
        help_text="Execution priority (higher first)"
    )

    # Rate limiting
    max_per_hour = models.IntegerField(
        null=True,
        blank=True,
        help_text="Rate limit per hour"
    )
    max_per_day = models.IntegerField(
        null=True,
        blank=True,
        help_text="Rate limit per day"
    )

    # Statistics
    times_triggered = models.IntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'name']
        verbose_name = "Notification Rule"
        verbose_name_plural = "Notification Rules"
        indexes = [
            models.Index(fields=['trigger_event', 'is_active']),
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return f"{self.name} (Priority: {self.priority})"

    def clean(self):
        """Validate rule data"""
        # Validate that integration and template types match
        if self.integration and self.template:
            if self.integration.provider.provider_type != self.template.template_type:
                raise ValidationError(
                    f"Integration type ({self.integration.provider.provider_type}) "
                    f"must match template type ({self.template.template_type})"
                )


class WebhookEndpoint(models.Model):
    """
    Webhook endpoints for receiving provider callbacks (delivery status, bounces, etc.).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='webhooks'
    )
    url = models.URLField(
        max_length=500,
        unique=True,
        help_text="Webhook URL"
    )
    secret = models.CharField(
        max_length=255,
        help_text="Webhook signing secret"
    )
    events = models.JSONField(
        default=list,
        help_text="List of events this webhook handles"
    )
    is_active = models.BooleanField(default=True)
    verify_signature = models.BooleanField(
        default=True,
        help_text="Whether to verify webhook signature"
    )

    # Statistics
    total_received = models.IntegerField(default=0)
    total_processed = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)

    last_received_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Webhook Endpoint"
        verbose_name_plural = "Webhook Endpoints"

    def __str__(self):
        return f"{self.integration.name} - {self.url}"

    @property
    def success_rate(self):
        """Calculate webhook processing success rate"""
        if self.total_received == 0:
            return 0
        return round((self.total_processed / self.total_received) * 100, 2)