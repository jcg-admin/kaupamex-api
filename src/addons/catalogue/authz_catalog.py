"""Declaración del catálogo L0 que dueña ``catalogue`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``catalogue`` — el addon homónimo dueña el catálogo de producto.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='catalogue',
        name='Catálogo',
        is_application=True,
        category='Order Management',
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='catalogue', name='Catálogo'),
]
