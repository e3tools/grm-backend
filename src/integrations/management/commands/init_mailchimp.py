# management/commands/test_mailchimp.py
from django.core.management.base import BaseCommand
from integrations.models import NotificationProvider, Integration
from integrations.base import get_adapter


class Command(BaseCommand):
    help = 'Test Mailchimp Transactional integration connection'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            help='Mailchimp Transactional API Key',
        )
        parser.add_argument(
            '--from-email',
            type=str,
            help='From email address (must be verified in Mailchimp)',
        )
        parser.add_argument(
            '--from-name',
            type=str,
            default='GRM Platform',
            help='From name (default: GRM Platform)',
        )
        parser.add_argument(
            '--reply-to',
            type=str,
            help='Reply-to email address (optional)',
        )
        parser.add_argument(
            '--create',
            action='store_true',
            help='Create the integration if it doesn\'t exist',
        )

    def handle(self, *args, **options):
        api_key = options.get('api_key')
        from_email = options.get('from_email')
        from_name = options.get('from_name')
        reply_to = options.get('reply_to')
        create = options.get('create')

        # Check if Mailchimp provider exists
        provider, created = NotificationProvider.objects.get_or_create(
            name='mailchimp',
            defaults={
                'display_name': 'Mailchimp Transactional',
                'provider_type': 'email',
                'supports_templates': True,
                'supports_tracking': True,
                'max_recipients_per_request': 1000,
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
            if not api_key or not from_email:
                self.stdout.write(
                    self.style.ERROR(
                        '[X] To create an integration, you must provide: '
                        '--api-key and --from-email'
                    )
                )
                return

            # Build configuration
            configuration = {
                'from_email': from_email,
                'from_name': from_name,
                'track_opens': True,
                'track_clicks': True,
            }

            if reply_to:
                configuration['reply_to'] = reply_to

            integration = Integration.objects.create(
                provider=provider,
                name='Mailchimp Transactional',
                status='active',
                credentials={
                    'api_key': api_key,
                },
                configuration=configuration,
                is_default=False,
                is_test_mode=True,
            )
            self.stdout.write(
                self.style.SUCCESS(f'[OK] Created Integration: {integration.name}')
            )

        elif not integration:
            self.stdout.write(
                self.style.WARNING(
                    '[!] No Mailchimp integration found. Use --create to create one.'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    '\nExample:\n'
                    'python manage.py test_mailchimp --create \\\n'
                    '  --api-key "md-xxxxx" \\\n'
                    '  --from-email "notifications@example.com" \\\n'
                    '  --from-name "GRM Platform" \\\n'
                    '  --reply-to "support@example.com"'
                )
            )
            return

        # Test connection
        self.stdout.write(
            self.style.WARNING('\n>> Testing connection to Mailchimp Transactional...')
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
                            f'\n  - Ping Response: {result["account_info"].get("ping")}'
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
