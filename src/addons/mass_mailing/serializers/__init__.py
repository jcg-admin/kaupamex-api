"""Serializers de la superficie admin de la newsletter (mass_mailing).

Un archivo por serializer (monolito modular), re-exportados aquí.
"""
from .campaign import (
    NEWSLETTER_STATUS_CHOICES,
    CampaignCreateSerializer,
    CampaignResponseSerializer,
)
from .subscriber import SubscriberListItemSerializer

__all__ = [
    'NEWSLETTER_STATUS_CHOICES',
    'CampaignCreateSerializer',
    'CampaignResponseSerializer',
    'SubscriberListItemSerializer',
]
