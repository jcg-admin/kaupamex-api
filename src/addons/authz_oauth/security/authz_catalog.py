"""Declaración del catálogo que dueña ``authz_oauth``.

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.

- ``permissions.oauth`` — acción nombrada (membresía) bajo el módulo
  ``permissions`` (que dueña ``authz``): gobierna el CRUD de proveedores
  OAuth2. Sensible: la referencia reserva ``auth.oauth.provider`` a
  ``base.group_system`` (``auth_oauth/security/ir.model.access.csv``). El
  endpoint de signin y la lista pública NO llevan capacidad — son superficie
  pre-auth (``auth='none'`` en la referencia).
"""
from addons.authz.declaration import CapabilitySpec

MODULES = []

CAPABILITIES = [
    CapabilitySpec(
        code='permissions.oauth', name='Federación OAuth2',
        is_sensitive=True,
    ),
]
