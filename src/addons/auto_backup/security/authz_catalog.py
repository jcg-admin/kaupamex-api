"""Declaración del catálogo L0 que dueña ``auto_backup`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``backups`` — ``auto_backup`` ejecuta y expone los respaldos.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(code='backups', name='Respaldos', category='Platform'),
]

CAPABILITIES = [
    CapabilitySpec(code='backups', name='Respaldos', is_sensitive=True),
]
