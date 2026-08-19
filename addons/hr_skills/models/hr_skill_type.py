"""``hr.skill.type`` — categoría de habilidad/certificación (addon ``hr_skills``).

Adaptación fiel de Odoo hr_skills/models/hr_skill_type.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte símbolo por símbolo — 7 campos + 5 métodos
==================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``active`` / ``sequence`` / ``name`` / ``color`` / ``is_certification``
       (``:17-24``)
     - portados verbatim
   * - ``skill_ids`` / ``skill_level_ids`` (One2many, ``:20-21``)
     - sin código — reverso automático de ``HrSkill.skill_type`` /
       ``HrSkillLevel.skill_type`` con ``related_name`` explícito
       (``skill_ids`` / ``skill_level_ids``)
   * - ``levels_count`` (compute+store, ``:23``)
     - portado — columna con default 0; el recómputo es
       ``_compute_levels_count()``, disponible pero sin motor de
       ``@api.depends`` que lo dispare (ver divergencia 1)
   * - ``_get_default_color`` (``:14-15``)
     - portado — función de módulo (regla del preámbulo: ``default=``
       siempre función nombrada, nunca lambda)
   * - ``_check_no_null_skill_or_skill_level`` (``:27-35``)
     - portado — método disponible, NO wireado a ``clean()`` (ver
       divergencia 2)
   * - ``_compute_display_name`` (``:37-43``)
     - portado — ``__str__``
   * - ``_compute_levels_count`` (``:45-52``)
     - portado — ``queryset.count()`` en vez de ``_read_group``
   * - ``_onchange_skill_level_ids`` (``:55-61``)
     - BLOQUEADO — ``@api.onchange`` es reactividad de formulario cliente;
       sin motor de onchange en este stack (0 consumidor)
   * - ``copy_data`` (``:63-73``)
     - BLOQUEADO — ``copy()``/``copy_data()`` genérico no existe en este
       árbol (medido ya en ``account_debit_note/wizard/
       account_debit_note.py``: 0 hits de ``def copy`` salvo
       ``ResConfigSettings.copy``, de otro dominio)

Divergencias declaradas
========================

1. **Sin motor ``@api.depends``.** ``levels_count`` no se recalcula solo al
   agregar/quitar niveles — ``_compute_levels_count()`` queda disponible
   para que el llamador (una futura vista/serializer) lo invoque tras
   escribir ``skill_level_ids``. Mismo criterio que ``hr.HrJob.skill_ids``
   (``addons/hr/models/hr_job.py`` de este mismo addon, ver más abajo).
2. **``_check_no_null_skill_or_skill_level`` NO se wirea a ``clean()``.**
   La referencia la dispara con ``@api.constrains('skill_ids',
   'skill_level_ids')`` — sólo al escribir esos campos, típicamente en el
   MISMO submit que ya trae skills y niveles. Wirearla a ``clean()`` haría
   fallar el ``save()`` de todo tipo de habilidad recién creado (todavía
   sin hijos). Queda como método explícito para quien complete el alta.
"""
import random

import fields

from addons.base.models import TimeStampedModel
from exceptions import ValidationError


def _get_default_color():
    """≙ ``_get_default_color`` (``:12-13``) — color aleatorio del type."""
    return random.randint(1, 11)


class HrSkillType(TimeStampedModel):
    """``hr.skill.type`` — el catálogo de tipos de habilidad/certificación."""

    _name = 'hr.skill.type'
    _description = 'Skill Type'
    _order = 'sequence, name'

    active = fields.Boolean(default=True, verbose_name='Activo')
    sequence = fields.Integer(default=0, verbose_name='Secuencia')
    name = fields.Char(
        max_length=255, required=True, translate=True, verbose_name='Nombre',
    )
    color = fields.Integer(
        default=_get_default_color, verbose_name='Color',
        help_text='Odoo color — aleatorio 1-11 al crear (_get_default_color).',
    )
    levels_count = fields.Integer(
        default=0, verbose_name='Nº de niveles',
        help_text='Odoo levels_count (compute+store, readonly=False) — '
                  'nº de hr.skill.level ligados a este tipo. Recómputo: '
                  '_compute_levels_count() (divergencia 1: sin @api.depends).',
    )
    is_certification = fields.Boolean(
        default=False, verbose_name='Certificación',
        help_text='Odoo is_certification — si está marcado, este tipo se '
                  'trata como certificación (fecha de validez, ícono).',
    )

    class Meta:
        db_table = 'hr_skill_type'
        ordering = ['sequence', 'name']
        verbose_name = 'Tipo de habilidad'
        verbose_name_plural = 'Tipos de habilidad'

    def __str__(self):
        """≙ ``_compute_display_name`` (``:35-40``) — sufijo de medalla
        militar (unicode) cuando es certificación."""
        if self.is_certification:
            return f'{self.name}\U0001F396'
        return self.name

    def _check_no_null_skill_or_skill_level(self):
        """≙ ``_check_no_null_skill_or_skill_level`` (``:26-33``).

        DISPONIBLE, no auto-wireada — ver divergencia 2 del docstring del
        módulo.
        """
        if not self.skill_ids.exists() or not self.skill_level_ids.exists():
            raise ValidationError(
                'El tipo de habilidad debe tener al menos una habilidad y '
                f'un nivel: {self.name}',
            )

    def _compute_levels_count(self):
        """≙ ``_compute_levels_count`` (``:42-48``) — cuenta directa en vez
        de ``_read_group`` (sin equivalente de agregación por grupo aquí)."""
        self.levels_count = self.skill_level_ids.count()
        return self.levels_count
