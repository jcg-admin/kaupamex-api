"""
Models — addons.payments.

``payments`` queda como **paquete controlador delgado** del framework de pagos:
webhooks, servicios, gateways (MercadoPago/PayPal), vistas y comandos. **No
tiene modelos propios.**

Los 6 modelos (``Payment``, ``Refund``, ``Chargeback``, ``PaymentGatewayEvent``,
``WebhookEvent``, ``SavedCard``) se movieron a su hogar fiel ``addons.payment``
(framework de pagos de Odoo: ``payment.transaction``/``payment.provider``/
``payment.token`` en el módulo ``payment``). Los consumidores importan desde
``addons.payment.models``.

La lógica específica de MercadoPago (``gateways/``, ``webhooks.py``,
``services.py``) se disuelve en el módulo de proveedor ``payment_mercado_pago``
en un pase posterior.
"""
# Compat de migración histórica: ``payments/migrations/0001_initial.py`` referencia
# ``addons.payments.models._make_verification_token`` como ``default=`` de
# ``SavedCard.verification_token``. Re-exportarlo mantiene esa migración importable
# tras mover el modelo a ``addons.payment`` (el default vivo ya apunta allí).
from addons.payment.models import _make_verification_token  # noqa: F401
