"""Modelos del addon ``observability`` -- unico addon net-new del arbol (DEC-12).

- ``request_log.py`` -> ``RequestLog`` (telemetria HTTP por request, DEC-LOG-01).
- ``business_event.py`` -> ``BusinessEvent`` (bitacora append-only de eventos
  de negocio, SOL-011). Sin analogo en la referencia; llego aqui al disolverse
  ``users`` en ``base`` (H-API-211).

Se reexporta aqui para preservar el contrato de import
``from addons.observability.models import RequestLog``.
"""
from .business_event import BusinessEvent
from .request_log import RequestLog

__all__ = [
    'BusinessEvent',
    'RequestLog',
]
