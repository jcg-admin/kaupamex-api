"""``hr.work.location`` — veto de borrado de sedes en uso.

Adaptación de Odoo hr_homeworking/models/hr_work_location.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 19 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte — 1 símbolo de la referencia
====================================

``_unlink_except_used_by_employee`` (``:12-19``) — portado, nombre y guion
bajo verbatim. Veta borrar una sede referida por el patrón semanal de algún
empleado; las excepciones puntuales (``hr.employee.location``) que la usen
se eliminan (la referencia hace lo mismo: ``unlink()`` explícito de las
excepciones, veto solo por los 7 campos semanales).

DIVERGENCIA declarada (la misma de ``hr/models/res_partner.py``,
``_unlink_contact_rel_employee``): el gancho ``@api.ondelete(at_uninstall=
False)`` no existe en este ORM — el flujo de borrado que se cablee sobre
``hr.work.location`` debe invocar este método antes de ``delete()``. El FK
``HrEmployeeLocation.work_location`` es ``PROTECT``, así que un ``delete()``
directo sin pasar por aquí falla ruidoso mientras existan excepciones.
"""
import models

from addons.hr.models.hr_employee import HrEmployee
from addons.hr_homeworking.models.hr_homeworking import DAYS, HrEmployeeLocation
from exceptions import UserError
from orm.model_classes import extend_model
from tools.translate import _


def _unlink_except_used_by_employee(self):
    """≙ ``_unlink_except_used_by_employee``
    (``odoo19c: hr_homeworking/models/hr_work_location.py:12-19``)."""
    day_filters = models.Q()
    for day in DAYS:
        day_filters |= models.Q(**{day: self})
    employee_uses_location = HrEmployee.objects.filter(day_filters).exists()
    if employee_uses_location:
        raise UserError(
            _('You cannot delete locations that are being used by your employees'),
        )
    HrEmployeeLocation.objects.filter(work_location=self).delete()


def apply_hr_homeworking_hr_work_location_extensions():
    """Cuelga el veto de borrado sobre ``hr.work.location`` — ≙
    ``_inherit``. Se invoca desde ``HrHomeworkingConfig.ready()``."""
    extend_model(
        'hr', 'HrWorkLocation',
        metodos={
            '_unlink_except_used_by_employee': _unlink_except_used_by_employee,
        },
    )
