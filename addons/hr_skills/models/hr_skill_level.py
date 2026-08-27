"""``hr.skill.level`` — un nivel dentro de un ``hr.skill.type``.

Adaptación fiel de Odoo hr_skills/models/hr_skill_level.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 4 campos + 1 constraint + 3 métodos
=================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``skill_type_id`` / ``name`` / ``level_progress`` / ``default_level``
       (``:12-15``)
     - portados verbatim
   * - ``technical_is_new_default`` (compute, sin store, ``:21``)
     - portado — propiedad; el compute de la referencia **siempre** devuelve
       ``False`` (nunca dispara por depends, a propósito), así que aquí es
       una propiedad constante — sin pérdida de fidelidad
   * - ``_check_level_progress`` (``models.Constraint``, ``:23-26``)
     - portado — ``Meta.constraints`` (``CheckConstraint``)
   * - ``_compute_technical_is_new_default`` (``:30-31``)
     - portado — el cuerpo de la propiedad de arriba
   * - ``create`` (``:34-39``) / ``write`` (``:41-44``)
     - portados, UNIFICADOS en ``save()`` — Django no distingue
       insert/update en la API pública de instancia; la invariante ("un solo
       ``default_level`` por tipo") es la misma en ambos casos de la
       referencia, así que un solo hook la cubre
"""
import fields
import models

from addons.base.models import TimeStampedModel


class HrSkillLevel(TimeStampedModel):
    """``hr.skill.level`` — un nivel de progreso dentro de un tipo."""

    _name = 'hr.skill.level'
    _description = 'Skill Level'
    _order = 'level_progress'

    skill_type = fields.Many2one(
        'hr_skills.HrSkillType', on_delete=models.CASCADE,
        null=True, blank=True, db_index=True,
        related_name='skill_level_ids', verbose_name='Tipo de habilidad',
    )
    name = fields.Char(required=True, verbose_name='Nombre')
    level_progress = fields.Integer(
        default=0, verbose_name='Progreso',
        help_text='Odoo level_progress — de 0 por ciento (sin conocimiento) '
                  'a 100 por ciento (dominio total).',
    )
    default_level = fields.Boolean(
        default=False, verbose_name='Nivel por defecto',
        help_text='Odoo default_level — si está marcado, este nivel se '
                  'preselecciona al elegir esta habilidad.',
    )

    class Meta:
        db_table = 'hr_skill_level'
        ordering = ['level_progress']
        verbose_name = 'Nivel de habilidad'
        verbose_name_plural = 'Niveles de habilidad'
        constraints = [
            # ≙ ``_check_level_progress`` (``:20-23``).
            models.CheckConstraint(
                condition=models.Q(level_progress__gte=0)
                & models.Q(level_progress__lte=100),
                name='hr_skill_level_progress_chk',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def technical_is_new_default(self):
        """≙ ``technical_is_new_default`` (``:15-18``) — el compute de la
        referencia siempre asigna ``False`` (campo técnico que sólo el
        front-end muta vía ``_onchange_skill_level_ids`` de
        ``hr.skill.type``, BLOQUEADO en ``hr_skill_type.py`` por ausencia
        de motor de onchange)."""
        return False

    def save(self, *args, **kwargs):
        """≙ ``create``/``write`` unificados (``:29-40``) — si este nivel
        queda marcado ``default_level``, desmarca a los demás niveles del
        mismo tipo."""
        super().save(*args, **kwargs)
        if self.default_level and self.skill_type_id:
            (self.skill_type.skill_level_ids
                .exclude(pk=self.pk)
                .update(default_level=False))
