"""Modelos del addon ``bus`` — paquete espejo de ``addons/bus/models/``.

Corrección de una afirmación que este índice sostenía
=====================================================

Decía: *"la referencia declara ocho ``_name``, pero sólo tres son modelos
nuevos (H-API-67) … Las otras cinco declaraciones extienden modelos del núcleo
de la referencia y **no aplican aquí**"*.

Dos cosas estaban mal, y la segunda es la grave:

1. **La cuenta.** ``ls addons/bus/models/`` da **11** archivos además del
   ``__init__``, no ocho: ``bus``, ``bus_listener_mixin``, ``ir_websocket``,
   ``ir_attachment``, ``ir_http``, ``ir_model``, ``ir_qweb``, ``res_groups``,
   ``res_partner``, ``res_users``, ``res_users_settings``. [PROVEN]
2. **"No aplican aquí"** es la forma exacta que H-API-134 prohíbe. Cinco de
   ellas **sí** aplican y están portadas: son las que hacen que un adjunto, un
   grupo, un partner, un usuario y sus ajustes sean canales del bus — con
   **tres delegaciones** de canal que el mixin ya recorría sin tener a quién
   delegar.

Lo que hay ahora, archivo por archivo
=====================================

Modelos propios del addon:

- ``bus.py`` → ``BusMessage`` (la cola; ``_gc_messages`` cierra H-API-140).
- ``bus_listener_mixin.py`` → ``BusListenerMixin`` + el registro
  ``CHANNEL_RESOLVERS``.
- ``ir_websocket.py`` → la **política de suscripción**
  (``build_bus_channel_list``, ``prepare_subscribe_data``). El transporte no;
  la política sí.

Extensiones de modelos de ``base`` — un archivo cada una, como allá:

- ``ir_attachment.py`` → emite en el canal del **usuario que actúa**.
- ``res_users.py`` → delega en su **partner**.
- ``res_users_settings.py`` → delega en su **usuario** (y de ahí al partner).
- ``res_partner.py`` / ``res_groups.py`` → **son** canal, no delegan; su
  archivo explica por qué eso es un dato y no una ausencia.

Aguas abajo del WebSocket que DEC-AF-06 descarta — el archivo existe con su
cadena de razones, sin contenido:

- ``ir_http.py`` (datos de apertura del socket) · ``ir_model.py``
  (definiciones para el cliente; aquí las publica OpenAPI) · ``ir_qweb.py``
  (bundle del worker; aquí empaqueta Webpack).
"""
from .bus import BusMessage
from .bus_listener_mixin import (
    BusListenerMixin,
    CHANNEL_RESOLVERS,
    register_channel,
)
from .ir_websocket import (
    BROADCAST_CHANNEL,
    build_bus_channel_list,
    prepare_subscribe_data,
)

# Importados por su efecto: registran su resolutor de canal al importarse.
from . import ir_attachment  # noqa: F401,E402
from . import res_users  # noqa: F401,E402
from . import res_users_settings  # noqa: F401,E402

__all__ = [
    'BusMessage',
    'BusListenerMixin',
    'CHANNEL_RESOLVERS',
    'register_channel',
    'BROADCAST_CHANNEL',
    'build_bus_channel_list',
    'prepare_subscribe_data',
]
