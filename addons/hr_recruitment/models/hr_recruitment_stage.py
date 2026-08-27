"""``hr.recruitment.stage`` — una etapa del embudo de reclutamiento (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/hr_recruitment_stage.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 55 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 12 de 14
========================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``name``…``is_warning_visible`` (12 campos, ``:12-35``)
     - portados
   * - ``default_get`` (``:37-42``)
     - BLOQUEADO — depende de ``self.env.context`` (formulario/kanban con
       ``default_job_id`` de la vista); este ORM no tiene contexto de
       request en el modelo (mismo criterio que ``ir_ui_menu.py`` de ``hr``)
   * - ``_compute_is_warning_visible`` (``:44-51``)
     - portado — ``record._origin`` (el valor pre-edición de un formulario
       Odoo) no tiene análogo aquí: se recibe el valor previo de
       ``hired_stage`` como argumento explícito en vez de leerlo de
       ``_origin`` (mismo criterio que ``resource_calendar_leaves.py``)

Divergencias declaradas
==========================

- ``legend_blocked``/``legend_waiting``/``legend_done``/``legend_normal``:
  la referencia usa ``default=lambda self: _('Blocked')`` — un ``default``
  de Django no acepta lambda (regla del proyecto); se usan funciones
  nombradas ``_default_legend_*``.
"""
from django.apps import apps

import fields
import models
from addons.base.models import TimeStampedModel
from tools.translate import _


def _default_legend_blocked():
    return _('Blocked')


def _default_legend_waiting():
    return _('Waiting')


def _default_legend_done():
    return _('Ready for Next Stage')


def _default_legend_normal():
    return _('In Progress')


class HrRecruitmentStage(TimeStampedModel):
    """``hr.recruitment.stage`` — una columna del kanban de reclutamiento."""

    _name = 'hr.recruitment.stage'
    _description = 'Recruitment Stages'
    _order = 'sequence'

    name = fields.Char(verbose_name='Nombre de la etapa')
    sequence = fields.Integer(default=10, verbose_name='Secuencia')
    jobs = fields.Many2many(
        'hr.HrJob', related_name='recruitment_stages', blank=True,
        verbose_name='Específica de puestos',
        help_text='Odoo job_ids: puestos que usan esta etapa. Otros puestos '
                  'no la usarán.',
    )
    requirements = fields.Text(blank=True, default='', verbose_name='Requisitos')
    template = fields.Many2one(
        'mail.MailTemplate', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hr_recruitment_stages', verbose_name='Plantilla de correo',
        help_text='Odoo template_id: se publica un mensaje sobre el '
                  'candidato con esta plantilla al entrar en la etapa.',
    )
    fold = fields.Boolean(
        default=False, verbose_name='Plegada en kanban',
        help_text='Esta etapa se pliega en la vista kanban cuando no hay '
                  'registros que mostrar.',
    )
    hired_stage = fields.Boolean(
        default=False, verbose_name='Etapa de contratación',
        help_text='Si se marca, esta etapa determina la fecha de '
                  'contratación de un candidato.',
    )
    rotting_threshold_days = fields.Integer(
        default=0, verbose_name='Días para viciarse',
        help_text='Días antes de que los candidatos en esta etapa se '
                  'consideren vencidos. 0 desactiva.',
    )
    legend_blocked = fields.Char(
        default=_default_legend_blocked,
        verbose_name='Etiqueta kanban roja',
    )
    legend_waiting = fields.Char(
        default=_default_legend_waiting,
        verbose_name='Etiqueta kanban naranja',
    )
    legend_done = fields.Char(
        default=_default_legend_done,
        verbose_name='Etiqueta kanban verde',
    )
    legend_normal = fields.Char(
        default=_default_legend_normal,
        verbose_name='Etiqueta kanban gris',
    )

    class Meta:
        db_table = 'hr_recruitment_stage'
        ordering = ['sequence']
        verbose_name = 'Etapa de reclutamiento'
        verbose_name_plural = 'Etapas de reclutamiento'

    def __str__(self) -> str:
        return self.name

    def is_warning_visible(self, was_hired_stage):
        """≙ ``_compute_is_warning_visible`` (``odoo19c: :44-51``).

        DIVERGENCIA: ``record._origin.hired_stage`` (el valor antes de la
        edición del formulario) se recibe como argumento explícito
        ``was_hired_stage`` — no hay formulario Odoo del que leerlo.

        ``apps.get_model`` (no un import al top): ``hr.applicant`` tiene una
        FK de vuelta a esta clase (``stage``), así que importarla aquí
        arriba cerraría un ciclo de import — excepción #3 de
        ``no-lazy-imports.md`` (llamada de función, no ``import`` léxico).
        """
        if not (was_hired_stage and not self.hired_stage):
            return False
        HrApplicant = apps.get_model('hr_recruitment', 'HrApplicant')
        return HrApplicant.objects.filter(stage=self).exists()
