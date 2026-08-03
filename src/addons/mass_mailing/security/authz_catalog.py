"""Declaración del catálogo L0 que dueña ``mass_mailing`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``newsletter`` — ``mass_mailing`` dueña campañas y suscriptores.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='newsletter',
        name='Newsletter',
        is_application=True,
        category='CRM',
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='newsletter', name='Newsletter'),
]
