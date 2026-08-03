"""Declaración del catálogo que dueña ``portal``.

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.

- ``permissions.portal`` — acción nombrada (membresía) bajo el módulo
  ``permissions``: gobierna la gestión de accesos de portal (conceder/
  revocar el acceso de un cliente a la plataforma; el ``portal.wizard`` de la
  referencia). Sensible: cambia quién puede entrar como cliente. La
  referencia reserva ese wizard a ``base.group_erp_manager``.

La lectura de un documento por ``access_token`` NO lleva capacidad: el token
ES la autorización (compartición por link, pre-auth), igual que la
referencia acepta el token en lugar del permiso.
"""
from addons.authz.declaration import CapabilitySpec

MODULES = []

CAPABILITIES = [
    CapabilitySpec(
        code='permissions.portal', name='Gestión de accesos de portal',
        is_sensitive=True,
    ),
]
