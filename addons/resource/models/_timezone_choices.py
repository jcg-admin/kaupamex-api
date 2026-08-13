"""Choices de zona horaria compartidas por ``resource.calendar`` y
``resource.resource`` (Odoo ``_tz_get``, ``base/models/res_partner.py``).

Divergencia declarada: la referencia arma la lista con ``pytz.common_timezones``;
aquí se usa ``zoneinfo.available_timezones()`` de la librería estándar —
``pytz`` no es dependencia de este proyecto y ``zoneinfo`` cubre el mismo
catálogo IANA sin agregar una dependencia nueva (stdlib desde Python 3.9;
el proyecto declara ``>=3.12,<3.15``).

Módulo interno (no exportado en ``models/__init__.py``) — sólo lo importan
los dos módulos de este addon que declaran un campo ``tz``.
"""
from zoneinfo import available_timezones

#: El nombre IANA más largo del catálogo estándar ronda 40 caracteres
#: (p. ej. ``America/Argentina/ComodRivadavia``, 33); 64 deja margen.
TZ_MAX_LENGTH = 64

TZ_CHOICES = sorted((name, name) for name in available_timezones())
