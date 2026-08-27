"""``hr.employee.public`` — indicador de hoja de horas, espejo público
(Odoo ``hr_timesheet``).

Adaptación de Odoo ``hr_timesheet/models/hr_employee_public.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 14 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST: 1 clase (``_inherit``), 1 campo, 1 método.

=================================  ==================================
Símbolo (línea)                    Desenlace
=================================  ==================================
``has_timesheet`` (:9)             **portado** — ``property``, delega en
                                    ``employee_id.has_timesheet`` (ya
                                    portada en ``models/hr_employee.py`` de
                                    este mismo addon).
``action_timesheet_from_employee`` **BLOQUEADO** — acción de UI
(:11-14)``                         (``self.employee_id.action_timesheet_
                                    from_employee()``, a su vez bloqueada
                                    en ``hr_employee.py``); sin cliente web.
=================================  ==================================

``hr.employee.public`` (``api: addons/hr/models/hr_employee_public.py``) es
una vista SQL denormalizada, no una FK propia: declara ``employee_id`` como
columna de la vista (``related_name='+'``, ``db_column='employee_id'``),
así que ``self.employee_id`` SÍ resuelve a la instancia de ``hr.HrEmployee``
— la delegación es directa, sin mecanismo adicional que construir.
"""
from addons.hr.models import HrEmployeePublic


def has_timesheet(self):
    """≙ ``has_timesheet`` (``odoo19c: hr_timesheet/models/
    hr_employee_public.py:9``, ``related='employee_id.has_timesheet'``)."""
    return bool(self.employee_id and self.employee_id.has_timesheet)


def apply_hr_timesheet_hr_employee_public_extensions():
    """Cuelga ``has_timesheet`` sobre ``hr.HrEmployeePublic``.

    La llama ``HrTimesheetConfig.ready()``. Requiere que ``models/
    hr_employee.py`` de este mismo addon ya haya colgado ``HrEmployee.
    has_timesheet`` — el orden de ``_EXTENSIONES`` en ``apps.py`` lo
    garantiza (``hr_employee`` antes que ``hr_employee_public``).
    """
    if not hasattr(HrEmployeePublic, 'has_timesheet'):
        HrEmployeePublic.has_timesheet = property(has_timesheet)
