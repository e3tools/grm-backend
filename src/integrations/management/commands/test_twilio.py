# management/commands/test_twilio.py
from django.core.management.base import BaseCommand
from integrations.models import NotificationProvider, Integration
from integrations.base import get_adapter


class Command(BaseCommand):
    help = 'Test Twilio integration connection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-sid',
            type=str,
            help='Twilio Account SID',
        )
        parser.add_argument(
            '--auth-token',
            type=str,
            help='Twilio Auth Token',
        )
        parser.add_argument(
            '--from-number',
            type=str,
            help='Twilio phone number (E.164 format, e.g., +15551234567)',
        )
        parser.add_argument(
            '--create',
            action='store_true',
            help='Create the integration if it doesn\'t exist',
        )

    def handle(self, *args, **options):
        account_sid = options.get('account_sid')
        auth_token = options.get('auth_token')
        from_number = options.get('from_number')
        create = options.get('create')

        # Check if Twilio provider exists
        provider, created = NotificationProvider.objects.get_or_create(
            name='twilio',
            defaults={
                'display_name': 'Twilio',
                'provider_type': 'sms',
                'supports_templates': False,
                'supports_tracking': False,
                'max_recipients_per_request': 1,
                'rate_limit_per_second': 10,
                'rate_limit_per_minute': 600,
                'is_active': True,
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created NotificationProvider: {provider.display_name}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Found existing NotificationProvider: {provider.display_name}')
            )

        # Check if integration exists
        integration = Integration.objects.filter(provider=provider).first()

        if not integration and create:
            if not account_sid or not auth_token or not from_number:
                self.stdout.write(
                    self.style.ERROR(
                        '✗ To create an integration, you must provide: '
                        '--account-sid, --auth-token, and --from-number'
                    )
                )
                return

            integration = Integration.objects.create(
                provider=provider,
                name='Twilio SMS',
                status='active',
                credentials={
                    'account_sid': account_sid,
                    'auth_token': auth_token,
                },
                configuration={
                    'from_number': from_number,
                },
                is_default=True,
                is_test_mode=True,
            )
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created Integration: {integration.name}')
            )

        elif not integration:
            self.stdout.write(
                self.style.WARNING(
                    '⚠ No Twilio integration found. Use --create to create one.'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    '\nExample:\n'
                    'python manage.py test_twilio --create \\\n'
                    '  --account-sid "ACxxxxx" \\\n'
                    '  --auth-token "your_token" \\\n'
                    '  --from-number "+15551234567"'
                )
            )
            return

        # Test connection
        self.stdout.write(
            self.style.WARNING('\n⏳ Testing connection to Twilio...')
        )

        try:
            adapter = get_adapter(integration)
            result = adapter.test_connection()

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f'\n✓ {result["message"]}')
                )
                if result.get('account_info'):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\nAccount Details:'
                            f'\n  - SID: {result["account_info"].get("sid")}'
                            f'\n  - Name: {result["account_info"].get("name")}'
                            f'\n  - Status: {result["account_info"].get("status")}'
                            f'\n  - Type: {result["account_info"].get("type")}'
                        )
                    )

                # Update integration test status
                from django.utils import timezone
                integration.last_test_at = timezone.now()
                integration.last_test_status = 'success'
                integration.last_test_message = result['message']
                integration.save()

            else:
                self.stdout.write(
                    self.style.ERROR(f'\n✗ {result["message"]}')
                )
                # Update integration test status
                from django.utils import timezone
                integration.last_test_at = timezone.now()
                integration.last_test_status = 'error'
                integration.last_test_message = result['message']
                integration.save()

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n✗ Error testing connection: {str(e)}')
            )
