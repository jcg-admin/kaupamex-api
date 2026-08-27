"""``hr.employee.public`` — las ubicaciones semanales en la ficha pública.

Adaptación de Odoo hr_homeworking/models/hr_employee_public.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 14 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte — 8 símbolos de la referencia (7 FKs + ``today_location_name``)
======================================================================

En la referencia ``hr.employee.public`` replica como columnas propias los 7
``<día>_location_id`` y ``today_location_name`` de ``hr.employee`` (el
modelo público de Odoo es una proyección SQL del privado). En este árbol
``hr.HrEmployeePublic`` ya expone los campos no-columna del empleado como
properties que delegan en ``employee_id`` (medido:
``hr/models/hr_employee_public.py`` — ``work_location_name``,
``hr_icon_display``, etc. son properties de delegación), así que los 8
símbolos siguen ese mismo camino: 8 properties de delegación.

DIVERGENCIA declarada: property en vez de columna — mismo criterio que las
del propio modelo público local; la fuente de verdad es el empleado, no una
copia.
"""
from orm.model_classes import extend_model


def _delegated_day_location(day_field_name):
    """Fábrica de las 7 properties de delegación (``employee_id.<día>``)."""
    def getter(self):
        if not self.employee_id_id:
            return None
        return getattr(self.employee_id, day_field_name)
    getter.__name__ = day_field_name
    getter.__doc__ = f'≙ ``{day_field_name}_id`` — delega en el empleado.'
    return getter


def today_location_name(self):
    """≙ ``today_location_name`` — delega en el empleado (que a su vez
    resuelve excepción-del-día o patrón semanal)."""
    return self.employee_id.today_location_name if self.employee_id_id else ''


def apply_hr_homeworking_hr_employee_public_extensions():
    """Cuelga sobre ``hr.employee.public`` las 8 properties de delegación —
    ≙ ``_inherit``. Se invoca desde ``HrHomeworkingConfig.ready()``."""
    extend_model(
        'hr', 'HrEmployeePublic',
        propiedades={
            'monday_location': _delegated_day_location('monday_location'),
            'tuesday_location': _delegated_day_location('tuesday_location'),
            'wednesday_location': _delegated_day_location('wednesday_location'),
            'thursday_location': _delegated_day_location('thursday_location'),
            'friday_location': _delegated_day_location('friday_location'),
            'saturday_location': _delegated_day_location('saturday_location'),
            'sunday_location': _delegated_day_location('sunday_location'),
            'today_location_name': today_location_name,
        },
    )
