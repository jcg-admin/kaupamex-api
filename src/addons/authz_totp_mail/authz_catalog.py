"""Declaración del catálogo que dueña ``authz_totp_mail``.

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.

- ``permissions.totp_invite`` — acción nombrada (membresía) bajo el módulo
  ``permissions``: la invitación de 2FA a otros usuarios
  (``action_totp_invite`` es una acción de administración de usuarios en la
  referencia). No sensible: no cambia credenciales de nadie — envía un
  correo de invitación.

El send/verify del código propio va con ``account.security`` (ya sembrada
en todos los roles, DEC-ENF-01) — no se declara capacidad nueva para eso.
"""
from addons.authz.declaration import CapabilitySpec

MODULES = []

CAPABILITIES = [
    CapabilitySpec(
        code='permissions.totp_invite', name='Invitar a activar 2FA',
    ),
]
