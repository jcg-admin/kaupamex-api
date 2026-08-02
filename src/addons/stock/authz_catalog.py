"""Declaración del catálogo L0 que dueña ``stock`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``returns`` — ``stock`` dueña ``ReturnRequest`` y su flujo.
- ``inventory`` — las existencias son ``stock.quant``; el addon ``inventory``
  se retiró (``api@9aabf56``) y su declaración quedó huérfana. ``stock`` es su
  dueño en la referencia: ``odoo19c: addons/stock/__manifest__.py`` declara
  ``category: 'Supply Chain/Inventory'`` (``odoo-tools@622ddc2a``).
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='returns',
        name='Devoluciones',
        is_application=True,
        category='Order Management',
        depends=('orders',),
    ),
    ModuleSpec(
        code='inventory',
        name='Inventario',
        is_application=True,
        category='Supply Chain Management',
        depends=('catalogue',),
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='returns', name='Devoluciones'),
    CapabilitySpec(code='inventory', name='Inventario'),
    CapabilitySpec(
        code='inventory.adjust',
        name='Ajustar existencias',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='inventory.import',
        name='Importar inventario',
        is_sensitive=True,
    ),
]
