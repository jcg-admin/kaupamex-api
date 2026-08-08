"""``ir.qweb`` extendido por ``bus`` — el bundle del worker de WebSocket.

Adaptación de ``addons/bus/models/ir_qweb.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 11 líneas).
``_get_bundles_to_pregenarate`` añade ``bus.websocket_worker_assets`` a los
bundles que se pre-generan, para que el worker esté listo antes de que el
cliente lo pida.

**No se porta el contenido**, por dos razones que se acumulan:

1. No hay worker de WebSocket que empaquetar — DEC-AF-06.
2. No hay pre-generación de bundles que extender: el empaquetado es Webpack en
   ``ui``, y ``assetsbundle.py`` de ``base`` ya declara esa decisión con su
   medición. La lista que este método extiende no existe de este lado.

Es la segunda razón la que hace que el archivo no pueda portarse ni siquiera
si mañana se adoptara el WebSocket: habría que añadir el worker al
``webpack.config.js`` de ``ui``, no a un método de ``ir.qweb``.
"""
