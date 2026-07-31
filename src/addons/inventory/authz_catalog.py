"""Declaración del catálogo L0 que dueña ``inventory`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``inventory`` — el addon homónimo dueña las existencias.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='inventory',
        name='Inventario',
        is_application=True,
        category='Supply Chain Management',
        depends=('catalogue',),
    ),
]

CAPABILITIES = [
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
