"""``ir.http`` extendido por ``bus`` — la info de sesión del WebSocket.

Adaptación de ``addons/bus/models/ir_http.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 19 líneas). Añade a
``get_frontend_session_info`` los datos que el cliente necesita para abrir el
WebSocket: la versión del worker y el intervalo de reintento.

**No se porta el contenido**, y la razón es anterior a este archivo: DEC-AF-06
descarta el transporte WebSocket —``pg_notify`` no existe en MariaDB, y el
bucle de entrega exigiría ASGI contra CNST-ARQ-001 (Apache + mod_wsgi)—. Sin
WebSocket que abrir no hay datos de apertura que enviar.

El archivo existe porque la referencia lo tiene y porque esta cadena
—extensión → transporte → decisión de arquitectura— es lo que se perdería al
no tenerlo: quien busque "dónde se le dice al cliente cómo conectar" encuentra
aquí la respuesta y su motivo, en vez de no encontrar nada.

Lo que este árbol hace en su lugar: el cliente **sondea**
(``BusMessage.poll``, ``bus/views.py``), y qué canales le tocan lo decide
``ir_websocket.build_bus_channel_list`` — que sí está portado, porque es
política, no transporte.
"""
