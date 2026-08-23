# management/commands/test_africastalking.py
from django.core.management.base import BaseCommand
from integrations.models import NotificationProvider, Integration
from integrations.base import get_adapter


class Command(BaseCommand):
    help = 'Test Africa\'s Talking integration connection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Africa\'s Talking username',
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='Africa\'s Talking API Key',
        )
        parser.add_argument(
            '--sender-id',
            type=str,
            default=None,
            help='Sender ID (default: None)',
        )
        parser.add_argument(
            '--create',
            action='store_true',
            help='Create the integration if it doesn\'t exist',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        api_key = options.get('api_key')
        sender_id = options.get('sender_id')
        create = options.get('create')

        # Check if Africa's Talking provider exists
        provider, created = NotificationProvider.objects.get_or_create(
            name='africas_talking',
            defaults={
                'display_name': 'Africa\'s Talking',
                'provider_type': 'sms',
                'supports_templates': False,
                'supports_tracking': True,
                'max_recipients_per_request': 1,
                'rate_limit_per_second': 10,
                'rate_limit_per_minute': 600,
                'is_active': True,
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'[OK] Created NotificationProvider: {provider.display_name}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'[OK] Found existing NotificationProvider: {provider.display_name}')
            )

        # Check if integration exists
        integration = Integration.objects.filter(provider=provider).first()

        if not integration and create:
            if not username or not api_key:
                self.stdout.write(
                    self.style.ERROR(
                        '[X] To create an integration, you must provide: '
                        '--username and --api-key'
                    )
                )
                return

            # Build configuration
            configuration = {
                'sender_id': sender_id,
            }

            integration = Integration.objects.create(
                provider=provider,
                name='Africa\'s Talking SMS',
                status='active',
                credentials={
                    'username': username,
                    'api_key': api_key,
                },
                configuration=configuration,
                is_default=False,
                is_test_mode=False,
            )
            self.stdout.write(
                self.style.SUCCESS(f'[OK] Created Integration: {integration.name}')
            )

        elif not integration:
            self.stdout.write(
                self.style.WARNING(
                    '[!] No Africa\'s Talking integration found. Use --create to create one.'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    '\nExample:\n'
                    'python manage.py test_africastalking --create \\\n'
                    '  --username "sandbox" \\\n'
                    '  --api-key "your_api_key_here" \\\n'
                    '  --sender-id "GRM"'
                )
            )
            return

        # Test connection
        self.stdout.write(
            self.style.WARNING('\n>> Testing connection to Africa\'s Talking...')
        )

        try:
            adapter = get_adapter(integration)
            result = adapter.test_connection()

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f'\n[OK] {result["message"]}')
                )
                if result.get('account_info'):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\nAccount Details:'
                            f'\n  - Username: {result["account_info"].get("username")}'
                            f'\n  - Balance: {result["account_info"].get("balance")}'
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
                    self.style.ERROR(f'\n[X] {result["message"]}')
                )
                # Update integration test status
                from django.utils import timezone
                integration.last_test_at = timezone.now()
                integration.last_test_status = 'error'
                integration.last_test_message = result['message']
                integration.save()

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n[X] Error testing connection: {str(e)}')
            )