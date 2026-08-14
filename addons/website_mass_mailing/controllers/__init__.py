"""Vistas de la superficie pública de la newsletter (website_mass_mailing).

Un archivo por endpoint/concern (monolito modular), re-exportados aquí para el
URLconf y los patches de test.
"""
from .confirm import NewsletterConfirmV2View, NewsletterConfirmView
from .subscribe import NewsletterSubscribeView
from .subscriptions import NewsletterSubscriptionsV2View
from .unsubscribe import NewsletterUnsubscribeView

__all__ = [
    'NewsletterSubscribeView',
    'NewsletterConfirmView',
    'NewsletterConfirmV2View',
    'NewsletterUnsubscribeView',
    'NewsletterSubscriptionsV2View',
]
