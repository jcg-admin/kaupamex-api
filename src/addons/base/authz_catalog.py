"""Declaración del catálogo L0 que dueña ``base`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.

Por qué estos códigos son de este addon: ``base`` dueña la identidad
(``res.users`` / ``res.partner``, ``odoo19c: odoo/addons/base/models/``), y
'Mi cuenta' es su cara de autoservicio. En la referencia el addon que declara
un modelo declara también sus derechos de acceso
(``<addon>/security/ir.model.access.csv``); aquí el análogo es este archivo.

**Procedencia.** Estas 16 capacidades vivían en ``users/authz_catalog.py``.
El commit ``api@6cf8120`` ("Move identity into base as res.partner and
res.users") movió los modelos pero **borró el catálogo sin re-alojarlo**: sin
él ``seed_authz`` no siembra ``account.*`` y todo gate ``HasCapability`` de
autoservicio responde 403 (fail-closed). Ver H-API-209.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    # ``users`` sobrevive como **módulo de catálogo**, no como addon: nombra el
    # dominio de administración de identidades. La referencia no tiene un addon
    # ``users`` (:ref:`analisis-users-no-es-un-addon-en-la-referencia`), pero sí
    # separa la gestión de usuarios como grupo de acceso propio.
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
