"""Declaración del catálogo L0 que dueña ``website`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``content`` — ``website`` dueña las páginas y piezas de contenido.
- ``seo`` — ``website`` dueña metadatos y rutas públicas.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(code='content', name='Contenido', category='Platform'),
    ModuleSpec(code='seo', name='SEO', category='Platform'),
]

CAPABILITIES = [
    CapabilitySpec(code='content', name='Contenido'),
    CapabilitySpec(code='seo', name='SEO'),
]
