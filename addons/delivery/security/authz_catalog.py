"""Declaración del catálogo L0 que dueña ``delivery`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``logistics`` — ``delivery`` dueña envíos, guías y transportistas.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='logistics',
        name='Logística',
        is_application=True,
        category='Order Management',
        depends=('orders',),
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='logistics', name='Logística'),
]
