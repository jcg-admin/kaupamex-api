"""``project.task`` — las habilidades de los asignados de la tarea.

Adaptación de Odoo project_hr_skills/models/project_task.py
(odoo-tools, odoo19c:, LGPL-3, 10 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 campo (medido por AST)
=====================================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia (línea)
     - Dónde queda aquí
   * - ``user_skill_ids``
       (One2many ``related='user_ids.employee_skill_ids'``, ``:10``)
     - propiedad — delega en el asignado (DIVERGENCIA única)

Divergencia declarada
======================

**``user_ids`` (M2M de asignados) es aquí ``assignee`` (FK única).** El
addon local ``project`` portó los asignados de la referencia como un solo
responsable (``project/models/project_task.py``: ``assignee``, help_text
"Odoo user_ids"); la cadena ``related`` colapsa a las habilidades del
empleado de ese único usuario, vía la propiedad ``employee_skill_ids`` que
``res_users.py`` de este mismo addon cuelga sobre ``res.users``.
"""
from addons.hr_skills.models.hr_employee_skill import HrEmployeeSkill
from orm.model_classes import extend_model


def user_skill_ids(self):
    """≙ ``user_skill_ids`` (``:10``,
    ``related='user_ids.employee_skill_ids'``) — queryset vacío cuando la
    tarea no tiene asignado."""
    if self.assignee_id is None:
        return HrEmployeeSkill.objects.none()
    return self.assignee.employee_skill_ids


def apply_project_hr_skills_project_task_extensions():
    """Cuelga sobre ``project.task`` las habilidades del asignado — ≙
    ``_inherit``. Se invoca desde ``ProjectHrSkillsConfig.ready()``."""
    extend_model(
        'project', 'ProjectTask',
        propiedades={
            'user_skill_ids': user_skill_ids,
        },
    )
