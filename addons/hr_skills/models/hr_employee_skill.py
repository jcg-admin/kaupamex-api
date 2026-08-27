"""``hr.employee.skill`` — el nivel de una habilidad de un empleado.

Adaptación fiel de Odoo hr_skills/models/hr_employee_skill.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 campo + 4 métodos
=================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``employee_id`` (``:13``)
     - portado verbatim
   * - ``_linked_field_name`` (``:15-16``)
     - portado — devuelve ``'employee'`` (nombre de campo Django, sin
       ``_id``)
   * - ``get_current_skills_by_employee`` (``:18-32``)
     - portado — DIVERGENCIA de firma: la referencia lo invoca como método
       de instancia del recordset (``self.employee_skill_ids.
       get_current_skills_by_employee()``); aquí, sin métodos propios sobre
       un ``QuerySet`` de Django, es ``classmethod`` que recibe el
       queryset como argumento
   * - ``open_hr_employee_skill_modal`` (``:34-45``)
     - BLOQUEADO — ``ir.actions.act_window`` (acción de cliente Odoo), sin
       equivalente en este stack DRF+React — misma familia (b) que
       ``res_partner.py`` de ``hr``
   * - ``action_save`` (``:47-48``)
     - BLOQUEADO — ``ir.actions.act_window_close``, ídem
"""
from collections import defaultdict
from datetime import date

import fields
import models

from addons.hr.models.hr_employee import HrEmployee
from addons.hr_skills.models.hr_individual_skill_mixin import HrIndividualSkillMixin


class HrEmployeeSkill(HrIndividualSkillMixin):
    """``hr.employee.skill`` — habilidad/certificación de un empleado."""

    _name = 'hr.employee.skill'
    _inherit = 'hr.individual.skill.mixin'
    _description = 'Skill level for employee'
    _order = 'skill_type_id, skill_level_id'
    _rec_name = 'skill_id'

    employee = fields.Many2one(
        HrEmployee, on_delete=models.CASCADE, db_index=True,
        related_name='employee_skill_ids', verbose_name='Empleado',
    )

    class Meta:
        db_table = 'hr_employee_skill'
        ordering = ['skill_type', 'skill_level']
        verbose_name = 'Habilidad de empleado'
        verbose_name_plural = 'Habilidades de empleado'

    def _linked_field_name(self):
        """≙ ``_linked_field_name`` (``:10-11``)."""
        return 'employee'

    @classmethod
    def get_current_skills_by_employee(cls, employee_skills):
        """≙ ``get_current_skills_by_employee`` (``:13-24``) — DIVERGENCIA
        de firma declarada en la tabla del docstring del módulo."""
        by_pair = defaultdict(list)
        for emp_skill in employee_skills:
            by_pair[(emp_skill.employee_id, emp_skill.skill_id)].append(emp_skill)
        today = date.today()
        result = defaultdict(list)
        for (employee_id, _skill_id), emp_skills in by_pair.items():
            active = [es for es in emp_skills
                      if not es.valid_to or es.valid_to >= today]
            if not active and emp_skills[0].is_certification:
                expired_valid_to = max(es.valid_to for es in emp_skills
                                        if es.valid_to)
                active = [es for es in emp_skills
                          if es.valid_to == expired_valid_to]
            result[employee_id].extend(active)
        return result

    def open_hr_employee_skill_modal(self):
        """BLOQUEADO — ``ir.actions.act_window`` (``:26-36``), ver la tabla
        del docstring del módulo."""
        raise NotImplementedError(
            'ir.actions.act_window sin equivalente — acción de cliente '
            'Odoo (familia (b)).',
        )

    def action_save(self):
        """BLOQUEADO — ``ir.actions.act_window_close`` (``:38-39``)."""
        raise NotImplementedError(
            'ir.actions.act_window_close sin equivalente — acción de '
            'cliente Odoo (familia (b)).',
        )
