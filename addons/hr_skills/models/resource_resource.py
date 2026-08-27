"""Extensión de ``resource.resource`` — las habilidades del empleado del
recurso.

Adaptación fiel de Odoo hr_skills/models/resource_resource.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 9 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03). Porte completo — 1 de 1 campo.

``employee_skill_ids`` (``related='employee_id.employee_skill_ids'``,
``:9``) — propiedad. ``resource.resource`` no declara un campo literal
``employee_id`` en este árbol (``addons/hr/models/resource.py`` lo deja
"sin código": el reverso real es
``resource.hr_hremployee_resource_mixin_set``, el ``related_name`` que
``ResourceMixin.resource`` genera). Se reutiliza el mismo helper que
``hr/models/resource.py`` ya declara para resolver "el empleado de este
recurso, o ``None``".
"""
from orm.model_classes import extend_model


def _first_employee(resource):
    """El empleado del recurso, o ``None`` — mismo helper que
    ``addons/hr/models/resource.py::_first_employee`` (duplicado local:
    cada addon resuelve su propio acceso al reverso del mixin, mismo
    criterio que el resto de las extensiones de este árbol)."""
    return resource.hr_hremployee_resource_mixin_set.first()


def employee_skill_ids(self):
    """≙ ``employee_skill_ids`` (``:9``)."""
    employee = _first_employee(self)
    return employee.employee_skill_ids.all() if employee is not None else []


def apply_hr_skills_resource_resource_extensions():
    """Cuelga sobre ``resource.resource`` lo que ``hr_skills`` le añade —
    ≙ ``_inherit``."""
    extend_model(
        'resource', 'ResourceResource',
        propiedades={
            'employee_skill_ids': employee_skill_ids,
        },
    )
