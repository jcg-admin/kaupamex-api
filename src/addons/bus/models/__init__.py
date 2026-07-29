"""Modelos del addon ``bus`` — paquete espejo de ``bus/models/`` (referencia).

La referencia declara ocho ``_name``, pero **sólo tres son modelos nuevos**
(H-API-67): ``bus.bus``, ``bus.listener.mixin`` e ``ir.websocket``. De esos, el
puerto adopta los dos primeros y deja fuera ``ir.websocket`` — es el extremo
del transporte WebSocket, que DEC-AF-06 descarta. Las otras cinco declaraciones
extienden modelos del núcleo de la referencia y no aplican aquí.

El mixin vive en ``mixins.py`` (no es un modelo Django: no aporta campos, igual
que el ``AbstractModel`` sin campos de la referencia).
"""
from .bus_bus import BusMessage

__all__ = ['BusMessage']
