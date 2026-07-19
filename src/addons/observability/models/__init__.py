"""Modelos del addon ``observability`` -- unico addon net-new del arbol (DEC-12).

- ``request_log.py`` -> ``RequestLog`` (telemetria HTTP por request, DEC-LOG-01).

Se reexporta aqui para preservar el contrato de import
``from addons.observability.models import RequestLog``.
"""
from .request_log import RequestLog

__all__ = [
    'RequestLog',
]
