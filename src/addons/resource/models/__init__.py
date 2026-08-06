"""Modelos del addon ``resource`` (estructura Odoo: un archivo por modelo).

Cierre parcial: los 5 ``_name``/``_inherit`` propios del addon (calendario,
sus tramos, sus ausencias, un recurso planificable, y el mixin abstracto que
los vincula a otros modelos) — el motor de intervalos fecha/hora de
``resource.calendar``/``resource.resource`` (``rrule``/``pytz`` en la
referencia) queda DEFERIDO por falta de consumidor, ver el docstring de
``resource_calendar.py`` y ``analisis-familia-resource``.
"""
from .resource_calendar_attendance import ResourceCalendarAttendance
from .resource_calendar_leaves import ResourceCalendarLeaves
from .resource_resource import ResourceResource
from .resource_mixin import ResourceMixin
from .resource_calendar import ResourceCalendar
from . import res_company  # noqa: F401 — análogo de _inherit sobre ResCompany
from . import res_users  # noqa: F401 — análogo de _inherit sobre ResUsers

__all__ = [
    'ResourceCalendarAttendance',
    'ResourceCalendarLeaves',
    'ResourceResource',
    'ResourceMixin',
    'ResourceCalendar',
]
