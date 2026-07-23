"""Modelos del addon ``payment`` — framework de pagos (hogar fiel Odoo).

Un archivo por modelo (monolito modular, como ``base/models/``):

- ``payment.py``        → ``Payment`` (~ ``payment.transaction``).
- ``refund.py``         → ``Refund`` (reembolso de la transacción).
- ``chargeback.py``     → ``Chargeback`` (contracargo del emisor).
- ``gateway_event.py``  → ``PaymentGatewayEvent`` (auditoría del proveedor).
- ``webhook_event.py``  → ``WebhookEvent`` (dedup de webhooks entrantes).
- ``saved_card.py``     → ``SavedCard`` (~ ``payment.token``).
- ``payment_provider.py`` → ``PaymentGateway`` (~ ``payment.provider``).

Movidos desde el addon no-Odoo ``payments`` (que queda como controlador). La
lógica específica de MercadoPago se disuelve en ``payment_mercado_pago``.
"""
from .payment import Payment
from .refund import Refund
from .chargeback import Chargeback
from .gateway_event import PaymentGatewayEvent
from .webhook_event import WebhookEvent
from .saved_card import SavedCard, _make_verification_token
from .payment_provider import PaymentGateway

__all__ = [
    'Payment',
    'Refund',
    'Chargeback',
    'PaymentGatewayEvent',
    'WebhookEvent',
    'SavedCard',
    '_make_verification_token',
    'PaymentGateway',
]
