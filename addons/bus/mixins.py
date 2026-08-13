"""Shim de compatibilidad — el hogar canónico es ``models/bus_listener_mixin.py``.

Este módulo **no** define nada: reexporta ``BusListenerMixin`` desde su archivo
canónico. Existe por una razón concreta y verificable, no por comodidad.

Por qué no se borra
===================

Dos migraciones de Django lo referencian **por ruta de módulo** en la lista de
bases de un modelo:

- ``addons/mail/migrations/0001_initial.py:1102`` →
  ``bases=(addons.bus.mixins.BusListenerMixin, models.Model)``
- ``addons/payment/migrations/0001_initial.py:165`` → idéntico.

Una migración aplicada es un **registro histórico**: describe el estado del
código en el momento en que se escribió, y Django la vuelve a importar cada vez
que reconstruye el grafo. Borrar el módulo rompe esa importación en cualquier
base que aún no haya llegado a la última migración; reescribir la migración
para que apunte al nuevo módulo falsea lo que había entonces.

El shim resuelve las dos cosas: el código nuevo importa del archivo canónico
—``addons.bus.models.bus_listener_mixin``, espejo de
``bus/models/bus_listener_mixin.py`` de la referencia— y las migraciones
existentes siguen resolviendo.
"""
from addons.bus.models.bus_listener_mixin import BusListenerMixin  # noqa: F401

__all__ = ['BusListenerMixin']
