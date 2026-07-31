"""Declaración del catálogo L0 que dueña ``reports`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``reports`` — el addon homónimo dueña la superficie de reporting.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='reports',
        name='Reportes',
        is_application=True,
        category='Finance',
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='reports', name='Reportes'),
    CapabilitySpec(code='reports.export', name='Exportar reportes'),
]
