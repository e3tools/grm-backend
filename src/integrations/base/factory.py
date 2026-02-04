# base/factory.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from integrations.models import Integration
    from integrations.base.providers import BaseNotificationAdapter


class AdapterNotFoundError(Exception):
    """Raised when no adapter is found for a provider"""
    pass


def get_adapter(integration: 'Integration') -> 'BaseNotificationAdapter':
    """
    Get the appropriate adapter instance for an integration

    Args:
        integration: Integration model instance

    Returns:
        BaseNotificationAdapter: Instantiated adapter for the provider

    Raises:
        AdapterNotFoundError: If no adapter is found for the provider
    """
    from integrations.providers.africas_talking import AfricasTalkingAdapter
    from integrations.providers.twilio import TwilioAdapter
    from integrations.providers.sendgrid import SendGridAdapter
    from integrations.providers.mailchimp import MailchimpAdapter
    from integrations.providers.klaviyo import KlaviyoAdapter

    # Mapping of provider names to adapter classes
    ADAPTER_MAP = {
        'africas_talking': AfricasTalkingAdapter,
        'twilio': TwilioAdapter,
        'sendgrid': SendGridAdapter,
        'mailchimp': MailchimpAdapter,
        'klaviyo': KlaviyoAdapter,
    }

    provider_name = integration.provider.name

    adapter_class = ADAPTER_MAP.get(provider_name)

    if not adapter_class:
        raise AdapterNotFoundError(
            f"No adapter found for provider: {provider_name}. "
            f"Available providers: {', '.join(ADAPTER_MAP.keys())}"
        )

    return adapter_class(integration)


def get_available_providers():
    """
    Get list of all available provider names

    Returns:
        List[str]: List of provider names that have adapters implemented
    """
    return [
        'africas_talking',
        'twilio',
        'sendgrid',
        'mailchimp',
        'klaviyo',
    ]