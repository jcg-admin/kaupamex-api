"""Modelos del addon ``hr_work_entry`` — espejo de
``odoo19c: hr_work_entry/models/`` (un archivo por modelo).

Se importan aquí SOLO los modelos concretos. Las extensiones sobre modelos
ajenos (``hr_employee``, ``hr_version``, ``resource_calendar``,
``resource_calendar_attendance``, ``resource_calendar_leaves``) se aplican
tarde desde ``HrWorkEntryConfig.ready()`` — el registro de modelos aún no
está poblado en tiempo de import de este paquete.

Orden: el tipo antes que la entrada — ``hr_work_entry.py`` importa
``HrWorkEntryType`` a nivel de módulo para sus defaults/helpers.
"""
from .hr_work_entry_type import HrWorkEntryType
from .hr_work_entry import HrWorkEntry
from .hr_user_work_entry_employee import HrUserWorkEntryEmployee

__all__ = ['HrWorkEntry', 'HrWorkEntryType', 'HrUserWorkEntryEmployee']
