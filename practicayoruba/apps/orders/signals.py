"""Signals — apps.orders. DEC-BC-19.

order_created: dispatched by CheckoutView when a new Order commits.
Notification wiring via apps.notifications.signals._order_value_created
(OrderValue.post_save); this module provides extensibility hooks for
future integrations (analytics, webhooks, etc.).
"""
from django.dispatch import Signal, receiver

order_created = Signal()


@receiver(order_created)
def _on_order_created(sender, order, user, total, **kwargs):
    """Stub — extensibility hook for future integrations."""
    pass
