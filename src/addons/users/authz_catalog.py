"""Declaración del catálogo L0 que dueña ``users`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.
Antes vivía en el propio seed como lista central; se movió aquí para que el
catálogo lo declare quien dueña el dominio, y no un archivo que hay que
recordar editar (H-API-106).

Por qué estos códigos son de este addon:

- ``users`` — el addon homónimo dueña la identidad.
- ``account`` — ``users`` dueña la identidad; 'Mi cuenta' es su cara de
  autoservicio.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(code='users', name='Usuarios', category='Platform'),
    ModuleSpec(code='account', name='Mi cuenta', category='Platform'),
]

CAPABILITIES = [
    CapabilitySpec(code='account.bus', name='Leer mi canal de eventos'),
    CapabilitySpec(code='account.deactivate', name='Dar de baja mi cuenta'),
    CapabilitySpec(
        code='account.notifications',
        name='Ver mis notificaciones',
    ),
    CapabilitySpec(code='account.orders', name='Ver mis pedidos'),
    CapabilitySpec(code='account.overview', name='Ver resumen de cuenta'),
    CapabilitySpec(code='account.password', name='Cambiar mi contraseña'),
    CapabilitySpec(
        code='account.payments',
        name='Ver mi historial y tarjetas',
    ),
    CapabilitySpec(code='account.profile', name='Ver mi perfil'),
    CapabilitySpec(
        code='account.referral',
        name='Ver mi programa de referidos',
    ),
    CapabilitySpec(code='account.returns', name='Ver mis devoluciones'),
    CapabilitySpec(code='account.reviews', name='Ver y escribir mis reseñas'),
    CapabilitySpec(
        code='account.security',
        name='Gestionar mi verificación 2FA',
    ),
    CapabilitySpec(
        code='account.shipments',
        name='Ver el seguimiento de mis envíos',
    ),
    CapabilitySpec(code='account.support', name='Ver mi soporte'),
    CapabilitySpec(code='account.wishlist', name='Ver mis favoritos'),
    CapabilitySpec(code='users', name='Usuarios', is_sensitive=True),
]
