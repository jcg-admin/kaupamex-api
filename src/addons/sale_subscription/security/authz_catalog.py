"""Declaración del catálogo L0 que dueña ``company`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``platform`` — ``company`` dueña las consolas L0 del operador Kaupamex.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(code='platform', name='Plataforma', category='Platform'),
]

CAPABILITIES = [
    CapabilitySpec(code='platform', name='Plataforma', is_sensitive=True),
    CapabilitySpec(
        code='platform.billing',
        name='Facturar y cobrar suscripciones (operador Kaupamex L0)',
        is_sensitive=True,
    ),
    CapabilitySpec(
        code='platform.provision',
        name='Provisionar la plataforma (operador Kaupamex L0)',
        is_sensitive=True,
    ),
]
