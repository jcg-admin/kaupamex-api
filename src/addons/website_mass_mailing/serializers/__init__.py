"""Serializers de la superficie pública de la newsletter (website_mass_mailing).

Un archivo por serializer (monolito modular), re-exportados aquí.
"""
from .subscribe import SubscribeSerializer
from .unsubscribe import UnsubscribeSerializer

__all__ = ['SubscribeSerializer', 'UnsubscribeSerializer']
