"""Vistas de la superficie admin de la newsletter (mass_mailing).

Un archivo por concern (monolito modular), re-exportados aquí para el URLconf.
"""
from .campaign import AdminCampaignCreateView
from .subscribers import (
    AdminSubscriberExportCSVView,
    AdminSubscriberForceUnsubscribeView,
    AdminSubscriberListView,
    AdminSubscriberSubscriptionDeleteView,
)

__all__ = [
    'AdminCampaignCreateView',
    'AdminSubscriberListView',
    'AdminSubscriberExportCSVView',
    'AdminSubscriberForceUnsubscribeView',
    'AdminSubscriberSubscriptionDeleteView',
]
