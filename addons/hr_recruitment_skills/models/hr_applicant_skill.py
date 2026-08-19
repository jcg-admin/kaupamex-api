"""``hr.applicant.skill`` — el nivel de una habilidad de un candidato.

Adaptación fiel de Odoo hr_recruitment_skills/models/hr_applicant_skill.py
(odoo-tools, odoo19c:, LGPL-3, 36 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 campo + 2 métodos (medido por AST: 6 attrs de
cabecera + 1 campo + 2 métodos en la fuente)
==========================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_name`` / ``_inherit`` / ``_description`` / ``_rec_name`` /
       ``_order`` (``:8-12``)
     - portados verbatim (cabecera completa — los 5 que la fuente declara)
   * - ``applicant_id`` (``:14-19``)
     - portado verbatim (``required``/``index``/``ondelete='cascade'``)
   * - ``_linked_field_name`` (``:21-22``)
     - portado — devuelve ``'applicant'`` (nombre de campo Django, sin
       ``_id``)
   * - ``_get_current_skills_by_applicant`` (``:24-36``)
     - portado — DIVERGENCIA de firma: la referencia lo invoca como método
       de instancia del recordset (``self.applicant_skill_ids.
       _get_current_skills_by_applicant()``); aquí, sin métodos propios
       sobre un ``QuerySet`` de Django, es ``classmethod`` que recibe el
       queryset/iterable como argumento — el MISMO criterio ya declarado
       por ``hr_skills/models/hr_employee_skill.py`` para
       ``get_current_skills_by_employee``

El protocolo de comandos x2many no aplica: los one2many de este árbol se
escriben con llamadas directas al manager (DIVERGENCIA 3 del docstring de
``hr_individual_skill_mixin.py``); este modelo hereda ese criterio.
"""
from collections import defaultdict
from datetime import date

import fields
import models

from addons.hr_recruitment.models.hr_applicant import HrApplicant
from addons.hr_skills.models.hr_individual_skill_mixin import HrIndividualSkillMixin


class HrApplicantSkill(HrIndividualSkillMixin):
    """``hr.applicant.skill`` — habilidad/certificación de un candidato."""

    _name = 'hr.applicant.skill'
    _inherit = 'hr.individual.skill.mixin'
    _description = 'Skill level for an applicant'
    _rec_name = 'skill_id'
    _order = 'skill_type_id, skill_level_id desc'

    applicant = fields.Many2one(
        HrApplicant, on_delete=models.CASCADE, db_index=True,
        related_name='applicant_skill_ids', verbose_name='Candidato',
    )

    class Meta:
        db_table = 'hr_applicant_skill'
        ordering = ['skill_type', '-skill_level']
        verbose_name = 'Habilidad de candidato'
        verbose_name_plural = 'Habilidades de candidato'

    def _linked_field_name(self):
        """≙ ``_linked_field_name`` (``:21-22``)."""
        return 'applicant'

    @classmethod
    def _get_current_skills_by_applicant(cls, applicant_skills):
        """≙ ``_get_current_skills_by_applicant`` (``:24-36``) — DIVERGENCIA
        de firma declarada en la tabla del docstring del módulo.

        Devuelve ``{applicant_pk: [HrApplicantSkill, …]}`` con las
        habilidades vigentes; para un tipo certificación sin vigentes,
        conserva la certificación más reciente (mismo criterio que la
        referencia y que ``get_current_skills_by_employee``).
        """
        by_pair = defaultdict(list)
        for applicant_skill in applicant_skills:
            by_pair[(applicant_skill.applicant_id,
                     applicant_skill.skill_id)].append(applicant_skill)
        today = date.today()
        result = defaultdict(list)
        for (applicant_id, _skill_id), applicant_skill_list in by_pair.items():
            active = [a_s for a_s in applicant_skill_list
                      if not a_s.valid_to or a_s.valid_to >= today]
            if not active and applicant_skill_list[0].is_certification:
                expired_valid_to = max(a_s.valid_to for a_s in applicant_skill_list
                                       if a_s.valid_to)
                active = [a_s for a_s in applicant_skill_list
                          if a_s.valid_to == expired_valid_to]
            result[applicant_id].extend(active)
        return result
