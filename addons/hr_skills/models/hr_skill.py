"""``hr.skill`` — una habilidad concreta dentro de un ``hr.skill.type``.

Adaptación fiel de Odoo hr_skills/models/hr_skill.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 4 campos + 1 método
=================================================

.. list-table::
   :header-rows: 1

   * - Símbolo
     - Estado
   * - ``name`` / ``sequence`` / ``skill_type_id`` (``:12-14``)
     - portados verbatim
   * - ``color`` (``related='skill_type_id.color'``, ``:15``)
     - propiedad — delega en ``skill_type``
   * - ``_compute_display_name`` (``:19-23``)
     - portado parcial — el ``__str__`` base devuelve ``name`` (rama
       ``from_skill_dropdown`` BLOQUEADA: ``@api.depends_context`` es
       reactividad de un dropdown de cliente Odoo sin equivalente aquí; el
       nombre con el tipo entre paréntesis queda como método aparte,
       disponible para quien construya ese widget)
"""
import fields
import models

from addons.base.models import TimeStampedModel


class HrSkill(TimeStampedModel):
    """``hr.skill`` — una habilidad, dentro de un tipo/categoría."""

    _name = 'hr.skill'
    _description = 'Skill'
    _order = 'sequence, name'

    name = fields.Char(
        required=True, translate=True, verbose_name='Nombre',
    )
    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    skill_type = fields.Many2one(
        'hr_skills.HrSkillType', on_delete=models.CASCADE, db_index=True,
        related_name='skill_ids', verbose_name='Tipo de habilidad',
    )

    class Meta:
        db_table = 'hr_skill'
        ordering = ['sequence', 'name']
        verbose_name = 'Habilidad'
        verbose_name_plural = 'Habilidades'

    def __str__(self):
        """≙ ``_compute_display_name`` (``:19-23``), rama por defecto (sin
        ``from_skill_dropdown``)."""
        return self.name

    @property
    def color(self):
        """≙ ``color`` (``related='skill_type_id.color'``)."""
        return self.skill_type.color if self.skill_type_id else 0

    def display_name_for_dropdown(self):
        """≙ ``_compute_display_name`` (``:19-23``), rama
        ``from_skill_dropdown`` — BLOQUEADA como cómputo automático (sin
        contexto de dropdown del cliente Odoo), disponible como método
        explícito para un futuro widget de selección."""
        skill_type_name = self.skill_type.name if self.skill_type_id else ''
        return f'{self.name} ({skill_type_name})'
