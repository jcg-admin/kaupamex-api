"""Declaración del catálogo L0 que dueña ``settings_app`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``banners`` — ``settings_app`` gatea los banners (config de sitio L1).
- ``settings`` — ``settings_app`` dueña la configuración de sitio.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(code='banners', name='Banners', category='CRM'),
    ModuleSpec(code='settings', name='Configuración', category='Platform'),
]

CAPABILITIES = [
    CapabilitySpec(code='banners', name='Banners'),
    CapabilitySpec(code='settings', name='Configuración', is_sensitive=True),
]
