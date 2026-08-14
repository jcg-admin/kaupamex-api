"""Declaración del catálogo L0 que dueña ``account`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``invoices`` — ``account`` dueña ``account.move`` — la factura es un
  asiento.
- ``finance`` — los movimientos financieros. El addon ``finance`` se retiró
  (``api@876768e``) y su declaración quedó huérfana; ``account`` es su dueño
  en la referencia, que declara ``category: 'Accounting/Accounting'``
  (``odoo19c: addons/account/__manifest__.py``, ``odoo-tools@622ddc2a``).

``invoices`` y ``finance`` son **dos** módulos, no uno: la factura es el
documento del continuo comercial (Order Management) y el movimiento
financiero es su contrapartida contable (Finance). Colapsarlos perdería esa
distinción, que es la misma que la referencia sostiene entre ``account.move``
y ``account.payment``.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='invoices',
        name='Facturas',
        is_application=True,
        category='Order Management',
        depends=('orders',),
    ),
    ModuleSpec(
        code='finance',
        name='Finanzas',
        is_application=True,
        category='Finance',
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='invoices', name='Facturas', is_sensitive=True),
    CapabilitySpec(code='finance', name='Finanzas', is_sensitive=True),
    CapabilitySpec(
        code='finance.close',
        name='Sellar corte de caja / cerrar ejercicio',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='finance.disburse',
        name='Pagar flete / cancelar-reembolsar cobro',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='finance.reconcile',
        name='Conciliar liquidaciones del gateway',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='finance.record',
        name='Registrar movimiento/concepto financiero',
        is_sensitive=True,
    ),
]
