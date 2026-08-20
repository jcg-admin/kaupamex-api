"""Modelos del addon ``observability``.

- ``business_event.py`` -> ``BusinessEvent`` (bitacora append-only de eventos
  de negocio, SOL-011). Sin analogo directo en la referencia; su contraparte
  funcional es ``mail.message`` + ``mail.tracking.value``, y su mudanza es la
  tarea **#497**.

``RequestLog`` **ya no vive aqui**: DEC-AF-11 lo partio en sus dos mitades —la
de error se fundio en ``ir.logging`` (``addons.base``) y la de acceso es
trabajo del ``access_log`` del proxy inverso—. El addon sobrevive solo mientras
``BusinessEvent`` espere su puente al chatter.
"""
from .business_event import BusinessEvent

__all__ = [
    'BusinessEvent',
]
