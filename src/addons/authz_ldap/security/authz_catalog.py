"""Declaración del catálogo que dueña ``authz_ldap``.

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.

- ``permissions.ldap`` — acción nombrada (membresía) bajo el módulo
  ``permissions`` (que dueña ``authz``): gobierna el CRUD de configuraciones
  LDAP y la prueba de conexión. Sensible: la referencia reserva
  ``res.company.ldap`` completo a ``base.group_system``
  (``auth_ldap/security/ir.model.access.csv``).
"""
from addons.authz.declaration import CapabilitySpec

MODULES = []

CAPABILITIES = [
    CapabilitySpec(
        code='permissions.ldap', name='Federación LDAP', is_sensitive=True,
    ),
]
