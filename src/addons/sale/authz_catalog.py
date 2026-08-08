"""Declaración del catálogo L0 que dueña ``sale`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``orders`` — ``sale`` dueña ``SaleOrder`` — la venta ES la orden
  (SOL-098).
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='orders',
        name='Pedidos',
        is_application=True,
        category='Order Management',
        # Las aristas vuelven: la condición que este comentario fijaba
        # ("cuando esas familias se integren") se cumplió. ``catalogue`` lo
        # declara ``product`` y ``inventory`` lo declara ``stock``, así que
        # ninguna de las dos es ya la arista colgada de H-API-106.
        depends=('catalogue', 'inventory'),
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='orders', name='Pedidos'),
]
