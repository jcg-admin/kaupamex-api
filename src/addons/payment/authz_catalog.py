"""Declaración del catálogo L0 que dueña ``payment`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.

Por qué este código es de este addon:

- ``payments`` — los cobros del comprador. El addon ``payments`` se retiró
  (``api@3be54aa``) y su declaración quedó huérfana; ``payment`` es quien
  dueña el dominio hoy (``PaymentProvider``, ``SavedCard``), igual que en la
  referencia (``odoo19c: addons/payment/models/payment_transaction.py``,
  ``odoo-tools@622ddc2a``).

Sensible: cobrar es una acción de dinero, así que la capacidad conserva su
``is_sensitive=True`` original (DEC-12 exige sesión elevada fresca).
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='payments',
        name='Pagos',
        is_application=True,
        category='Order Management',
        depends=('orders',),
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='payments', name='Pagos', is_sensitive=True),
]
