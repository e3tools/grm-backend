# base/__init__.py
from integrations.base.providers import BaseNotificationAdapter
from integrations.base.factory import get_adapter, get_available_providers, AdapterNotFoundError

__all__ = [
    'BaseNotificationAdapter',
    'get_adapter',
    'get_available_providers',
    'AdapterNotFoundError',
]