# providers/__init__.py
from integrations.providers.twilio import TwilioAdapter
from integrations.providers.sendgrid import SendGridAdapter
from integrations.providers.mailchimp import MailchimpAdapter
from integrations.providers.klaviyo import KlaviyoAdapter
from integrations.providers.africas_talking import AfricasTalkingAdapter

__all__ = [
    'TwilioAdapter',
    'SendGridAdapter',
    'MailchimpAdapter',
    'KlaviyoAdapter',
    'AfricasTalkingAdapter',
]