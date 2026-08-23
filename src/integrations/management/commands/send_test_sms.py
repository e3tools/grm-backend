# management/commands/send_test_sms.py
from django.core.management.base import BaseCommand
from integrations.models import Integration
from integrations.services import SMSService, NotificationService


class Command(BaseCommand):
    help = 'Send a test SMS using Twilio, Africa\'s Talking, or another SMS integration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            required=True,
            help='Recipient phone number in E.164 format (e.g., +15551234567)',
        )
        parser.add_argument(
            '--message',
            type=str,
            default='Hello from GRM Platform! This is a test SMS.',
            help='Message to send',
        )
        parser.add_argument(
            '--integration-id',
            type=str,
            help='Integration ID to use (optional, defaults to active SMS integration)',
        )
        parser.add_argument(
            '--provider',
            type=str,
            choices=['twilio', 'africas_talking'],
            help='Specific provider to use (optional, defaults to default SMS integration)',
        )
        parser.add_argument(
            '--service',
            type=str,
            default='notification',
            choices=['sms', 'notification'],
            help='Which service to use: "sms" for SMSService or "notification" for NotificationService',
        )

    def handle(self, *args, **options):
        recipient = options['to']
        message = options['message']
        integration_id = options.get('integration_id')
        provider = options.get('provider')
        service_type = options['service']

        self.stdout.write(
            self.style.WARNING('\n========================================')
        )
        self.stdout.write(
            self.style.WARNING('>> Sending Test SMS')
        )
        self.stdout.write(
            self.style.WARNING('========================================')
        )
        self.stdout.write(f'\nRecipient: {recipient}')
        self.stdout.write(f'Message: {message}')
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
                provider__provider_type='sms',
                status='active'
            ).first()

            if not integration:
                self.stdout.write(
                    self.style.ERROR(f'\n[X] No active {provider} integration found')
                )
                return

            self.stdout.write(f'Integration: {integration.name} ({integration.provider.display_name})')

        else:
            # Get default SMS integration
            integration = Integration.objects.filter(
                provider__provider_type='sms',
                is_default=True,
                status='active'
            ).first()

            if not integration:
                self.stdout.write(
                    self.style.ERROR('\n[X] No active SMS integration found')
                )
                self.stdout.write(
                    self.style.WARNING(
                        '\nTip: Create an SMS integration first:\n\n'
                        'For Twilio:\n'
                        'python manage.py test_twilio --create \\\n'
                        '  --account-sid "AC..." \\\n'
                        '  --auth-token "..." \\\n'
                        '  --from-number "+1..."\n\n'
                        'For Africa\'s Talking:\n'
                        'python manage.py test_africastalking --create \\\n'
                        '  --username "sandbox" \\\n'
                        '  --api-key "..." \\\n'
                        '  --sender-id "GRM"'
                    )
                )
                return

            self.stdout.write(f'Integration: {integration.name} ({integration.provider.display_name})')

        # Display configuration
        self.stdout.write('\n' + '-' * 40)
        self.stdout.write('Sending SMS...\n')

        # Send SMS using the selected service
        try:
            if service_type == 'sms':
                log = SMSService.send_sms(
                    recipient=recipient,
                    message=message,
                    integration=integration
                )
            else:  # notification
                log = NotificationService.send_sms(
                    recipient=recipient,
                    message=message,
                    integration=integration
                )

            # Display results
            if log.status == 'sent':
                self.stdout.write(
                    self.style.SUCCESS('\n[OK] SMS sent successfully!')
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nDetails:'
                        f'\n  - Log ID: {log.id}'
                        f'\n  - Status: {log.status}'
                        f'\n  - Provider Message ID: {log.provider_message_id}'
                        f'\n  - Sent At: {log.sent_at}'
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
                    for key, value in log.provider_response.items():
                        self.stdout.write(f'  - {key}: {value}')

                # Update integration stats
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nIntegration Stats:'
                        f'\n  - Total Sent: {integration.total_sent}'
                        f'\n  - Total Delivered: {integration.total_delivered}'
                        f'\n  - Total Failed: {integration.total_failed}'
                        f'\n  - Success Rate: {integration.success_rate}%'
                    )
                )

            else:
                self.stdout.write(
                    self.style.ERROR('\n[X] SMS failed to send')
                )
                self.stdout.write(
                    self.style.ERROR(
                        f'\nError Details:'
                        f'\n  - Status: {log.status}'
                        f'\n  - Error: {log.error_message}'
                        f'\n  - Failed At: {log.failed_at}'
                    )
                )

                if log.provider_response:
                    self.stdout.write(
                        self.style.ERROR(
                            f'\nProvider Response: {log.provider_response}'
                        )
                    )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n[X] Error sending SMS: {str(e)}')
            )
            import traceback
            self.stdout.write(
                self.style.ERROR(f'\nTraceback:\n{traceback.format_exc()}')
            )