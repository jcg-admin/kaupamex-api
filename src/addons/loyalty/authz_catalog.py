"""Declaración del catálogo L0 que dueña ``loyalty`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``vouchers`` — ``loyalty`` dueña cupones y programas.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='vouchers',
        name='Cupones',
        is_application=True,
        category='Order Management',
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='vouchers', name='Cupones'),
]
