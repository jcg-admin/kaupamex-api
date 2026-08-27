"""``res.users`` — las habilidades del empleado del usuario.

Adaptación de Odoo project_hr_skills/models/res_users.py
(odoo-tools, odoo19c:, LGPL-3, 8 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 campo (medido por AST)
=====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Dónde queda aquí
   * - ``employee_skill_ids``
       (One2many ``related='employee_id.employee_skill_ids'``, ``:8``)
     - propiedad — delega en ``self.employee`` (la propiedad que la
       extensión de ``hr`` sobre ``res.users`` ya expone:
       ``addons/hr/models/res_users.py``, el empleado de la empresa
       activa). Es exactamente la cadena ``related`` de la referencia, con
       el mismo criterio "related sin store → propiedad" de
       ``hr_fleet/models/employee.py``
"""
from addons.hr_skills.models.hr_employee_skill import HrEmployeeSkill
from orm.model_classes import extend_model


def employee_skill_ids(self):
    """≙ ``employee_skill_ids`` (``:8``,
    ``related='employee_id.employee_skill_ids'``) — queryset vacío cuando
    el usuario no tiene empleado ligado."""
    employee = self.employee
    if employee is None:
        return HrEmployeeSkill.objects.none()
    return employee.employee_skill_ids.all()


def apply_project_hr_skills_res_users_extensions():
    """Cuelga sobre ``res.users`` la delegación de habilidades — ≙
    ``_inherit``. Se invoca desde ``ProjectHrSkillsConfig.ready()``."""
    extend_model(
        'base', 'ResUsers',
        propiedades={
            'employee_skill_ids': employee_skill_ids,
        },
    )
