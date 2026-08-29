# management/commands/send_test_email.py
from django.core.management.base import BaseCommand
from integrations.models import Integration
from integrations.services import EmailService, NotificationService


class Command(BaseCommand):
    help = 'Send a test email using SendGrid or another email integration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            required=True,
            help='Recipient email address',
        )
        parser.add_argument(
            '--subject',
            type=str,
            default='Test Email from GRM Platform',
            help='Email subject line',
        )
        parser.add_argument(
            '--body',
            type=str,
            default='Hello! This is a test email from the GRM Platform notification system.',
            help='Plain text email body',
        )
        parser.add_argument(
            '--html',
            action='store_true',
            help='Send HTML email with default template',
        )
        parser.add_argument(
            '--html-body',
            type=str,
            help='Custom HTML email body (overrides --html)',
        )
        parser.add_argument(
            '--integration-id',
            type=str,
            help='Integration ID to use (optional, defaults to active email integration)',
        )
        parser.add_argument(
            '--provider',
            type=str,
            choices=['sendgrid', 'mailchimp'],
            help='Specific provider to use (optional, defaults to default email integration)',
        )
        parser.add_argument(
            '--service',
            type=str,
            default='email',
            choices=['email', 'notification'],
            help='Which service to use: "email" for EmailService or "notification" for NotificationService',
        )

    def handle(self, *args, **options):
        recipient = options['to']
        subject = options['subject']
        body = options['body']
        html_body = options.get('html_body')
        use_html = options.get('html')
        integration_id = options.get('integration_id')
        provider = options.get('provider')
        service_type = options['service']

        # Generate default HTML body if --html flag is used
        if use_html and not html_body:
            html_body = self._generate_html_template(subject, body)

        self.stdout.write(
            self.style.WARNING('\n========================================')
        )
        self.stdout.write(
            self.style.WARNING('>> Sending Test Email')
        )
        self.stdout.write(
            self.style.WARNING('========================================')
        )
        self.stdout.write(f'\nRecipient: {recipient}')
        self.stdout.write(f'Subject: {subject}')
        self.stdout.write(f'Body: {body[:100]}{"..." if len(body) > 100 else ""}')
        if html_body:
            self.stdout.write(f'HTML Email: Yes ({"custom" if options.get("html_body") else "default template"})')
        self.stdout.write(f'Service: {service_type.upper()}Service\n')

        # Get integration if specified
        integration = None
        if integration_id:
            try:
                integration = Integration.objects.get(id=integration_id)
                self.stdout.write(f'Integration: {integration.name}')
            except Integration.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'\n[X] Integration with ID {integration_id} not found')
                )
                return
        elif provider:
            # Get integration by provider name
            integration = Integration.objects.filter(
                provider__name=provider,
                provider__provider_type='email',
                status='active'
            ).first()

            if not integration:
                self.stdout.write(
                    self.style.ERROR(f'\n[X] No active {provider} integration found')
                )
                return

            self.stdout.write(f'Integration: {integration.name} ({integration.provider.display_name})')

        else:
            # Get default email integration
            integration = Integration.objects.filter(
                provider__provider_type='email',
                is_default=True,
                status='active'
            ).first()

            if not integration:
                self.stdout.write(
                    self.style.ERROR('\n[X] No active email integration found')
                )
                self.stdout.write(
                    self.style.WARNING(
                        '\nTip: Create an email integration first:\n\n'
                        'For SendGrid:\n'
                        'python manage.py test_sendgrid --create \\\n'
                        '  --api-key "SG.xxxxx" \\\n'
                        '  --api-key-id "xxxxx" \\\n'
                        '  --from-email "your-email@example.com"\n\n'
                        'For Mailchimp Transactional:\n'
                        'python manage.py test_mailchimp --create \\\n'
                        '  --api-key "md-xxxxx" \\\n'
                        '  --from-email "your-email@example.com"'
                    )
                )
                return

            self.stdout.write(f'Integration: {integration.name} ({integration.provider.display_name})')

        # Display integration configuration
        self.stdout.write(f'From: {integration.configuration.get("from_email")} ({integration.configuration.get("from_name")})')
        if integration.configuration.get('reply_to'):
            self.stdout.write(f'Reply-To: {integration.configuration.get("reply_to")}')

        self.stdout.write('\n' + '-' * 40)
        self.stdout.write('Sending email...\n')

        # Send email using the selected service
        try:
            if service_type == 'email':
                log = EmailService.send_email(
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                    integration=integration
                )
            else:  # notification
                log = NotificationService.send_email(
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                    integration=integration
                )

            # Display results
            if log.status == 'sent':
                self.stdout.write(
                    self.style.SUCCESS('\n========================================')
                )
                self.stdout.write(
                    self.style.SUCCESS('[OK] Email sent successfully!')
                )
                self.stdout.write(
                    self.style.SUCCESS('========================================')
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nEmail Details:'
                        f'\n  - Log ID: {log.id}'
                        f'\n  - Status: {log.status}'
                        f'\n  - Provider Message ID: {log.provider_message_id}'
                        f'\n  - Sent At: {log.sent_at.strftime("%Y-%m-%d %H:%M:%S") if log.sent_at else "N/A"}'
                    )
                )

                # Display cost if available
                if log.cost:
                    self.stdout.write(
                        self.style.SUCCESS(f'  - Cost: ${log.cost}')
                    )

                # Display provider response details
                if log.provider_response:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\nProvider Response:'
                        )
                    )
                    status_code = log.provider_response.get('status_code', 'N/A')
                    self.stdout.write(f'  - Status Code: {status_code}')

                    headers = log.provider_response.get('headers', {})
                    if headers and isinstance(headers, dict):
                        message_id = headers.get('X-Message-Id', 'N/A')
                        self.stdout.write(f'  - Message ID: {message_id}')

                # Display integration stats
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nIntegration Stats ({integration.name}):'
                        f'\n  - Total Sent: {integration.total_sent}'
                        f'\n  - Total Delivered: {integration.total_delivered}'
                        f'\n  - Total Failed: {integration.total_failed}'
                        f'\n  - Success Rate: {integration.success_rate}%'
                    )
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n========================================\n'
                        f'Check your inbox at: {recipient}\n'
                        f'========================================\n'
                    )
                )

            else:
                self.stdout.write(
                    self.style.ERROR('\n========================================')
                )
                self.stdout.write(
                    self.style.ERROR('[X] Email failed to send')
                )
                self.stdout.write(
                    self.style.ERROR('========================================')
                )
                self.stdout.write(
                    self.style.ERROR(
                        f'\nError Details:'
                        f'\n  - Status: {log.status}'
                        f'\n  - Error: {log.error_message}'
                        f'\n  - Failed At: {log.failed_at.strftime("%Y-%m-%d %H:%M:%S") if log.failed_at else "N/A"}'
                    )
                )

                if log.provider_response:
                    self.stdout.write(
                        self.style.ERROR(
                            f'\nProvider Response:'
                        )
                    )
                    for key, value in log.provider_response.items():
                        # Truncate long values
                        value_str = str(value)
                        if len(value_str) > 200:
                            value_str = value_str[:200] + '...'
                        self.stdout.write(f'  - {key}: {value_str}')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR('\n========================================')
            )
            self.stdout.write(
                self.style.ERROR(f'[X] Error sending email: {str(e)}')
            )
            self.stdout.write(
                self.style.ERROR('========================================')
            )
            import traceback
            self.stdout.write(
                self.style.ERROR(f'\nTraceback:\n{traceback.format_exc()}')
            )

    def _generate_html_template(self, subject, body):
        """Generate a nice HTML template for the email"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td align="center" style="padding: 40px 0;">
                <table role="presentation" style="width: 600px; border-collapse: collapse; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 30px; background-color: #2c3e50; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px;">GRM Platform</h1>
                            <p style="margin: 10px 0 0 0; color: #ecf0f1; font-size: 14px;">Grievance Redressal Mechanism</p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="margin: 0 0 20px 0; color: #2c3e50; font-size: 24px;">{subject}</h2>
                            <p style="margin: 0 0 15px 0; color: #333333; font-size: 16px; line-height: 1.6;">
                                {body}
                            </p>
                            <div style="margin-top: 30px; padding: 20px; background-color: #ecf0f1; border-radius: 5px;">
                                <p style="margin: 0; color: #555555; font-size: 14px; line-height: 1.5;">
                                    <strong>Note:</strong> This is a test email from the GRM Platform notification system.
                                    If you received this email, it means the email integration is working correctly.
                                </p>
                            </div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 30px; background-color: #f8f9fa; text-align: center; border-top: 1px solid #dee2e6;">
                            <p style="margin: 0 0 10px 0; color: #6c757d; font-size: 14px;">
                                GRM Platform - Notification System
                            </p>
                            <p style="margin: 0; color: #6c757d; font-size: 12px;">
                                Powered by SendGrid | Test Email Sent at {self._get_current_time()}
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    def _get_current_time(self):
        """Get current time formatted"""
        from django.utils import timezone
        return timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')