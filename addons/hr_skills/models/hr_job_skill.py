"""``hr.job.skill`` — el nivel de una habilidad requerida por un puesto.

Adaptación fiel de Odoo hr_skills/models/hr_job_skill.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03). Porte completo — 1 campo + 2 métodos, 3 de 3.

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``job_id`` (``:13-18``)
     - portado verbatim
   * - ``_linked_field_name`` (``:20-21``)
     - portado — devuelve ``'job'`` (nombre de campo Django, sin ``_id``)
   * - ``_can_edit_certification_validity_period`` (``:23-24``)
     - portado verbatim (override a ``False``)
"""
import fields
import models

from addons.hr.models.hr_job import HrJob
from addons.hr_skills.models.hr_individual_skill_mixin import HrIndividualSkillMixin


class HrJobSkill(HrIndividualSkillMixin):
    """``hr.job.skill`` — habilidad requerida por un puesto."""

    _name = 'hr.job.skill'
    _inherit = 'hr.individual.skill.mixin'
    _description = 'Skills for job positions'
    _order = 'skill_type_id, skill_level_id desc'
    _rec_name = 'skill_id'

    job = fields.Many2one(
        HrJob, on_delete=models.CASCADE, db_index=True,
        related_name='job_skill_ids', verbose_name='Puesto',
    )

    class Meta:
        db_table = 'hr_job_skill'
        ordering = ['skill_type', '-skill_level']
        verbose_name = 'Habilidad de puesto'
        verbose_name_plural = 'Habilidades de puesto'

    def _linked_field_name(self):
        """≙ ``_linked_field_name`` (``:15-16``)."""
        return 'job'

    def _can_edit_certification_validity_period(self):
        """≙ ``_can_edit_certification_validity_period`` (``:18-19``) —
        override a ``False``: un puesto no admite varias certificaciones
        idénticas con distinto rango de fecha."""
        return False
