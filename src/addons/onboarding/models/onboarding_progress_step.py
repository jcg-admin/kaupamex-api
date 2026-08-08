"""``onboarding.progress.step`` — addon ``onboarding``.

Adaptación fiel de Odoo onboarding/models/onboarding_progress_step.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Trackea el progreso de UN ``onboarding.onboarding.step``, opcionalmente por
compañía (``odoo19c: onboarding_progress_step.py:16-19``).

**Divergencia de forma (recordset -> instancia).** ``action_consolidate_
just_done``/``action_set_just_done`` operan en la referencia sobre un
recordset (``self`` puede contener 0..N filas) porque Odoo opera siempre en
lote. Django no tiene recordsets: se portan como método de instancia (el
caso de uso real, un step a la vez, vía
``OnboardingOnboardingStep.action_set_just_done``) MÁS un classmethod de lote
(``consolidate_just_done_queryset``) para el caso plural de
``OnboardingProgress.get_and_update_onboarding_state``.
"""
from django.db import models
from django.db.models.functions import Coalesce

import fields

from addons.onboarding.models.onboarding_progress import (
    ONBOARDING_PROGRESS_STATES,
    STATE_DONE,
    STATE_JUST_DONE,
    STATE_NOT_DONE,
)
from addons.base.models.timestamped_mixin import TimeStampedModel


class OnboardingProgressStep(TimeStampedModel):
    """``onboarding.progress.step`` — tracker de progreso de un paso."""

    # Odoo step_id (onboarding_progress_step.py:16-17, required, ondelete
    # cascade, index).
    step = fields.Many2one(
        'onboarding.OnboardingOnboardingStep', on_delete=models.CASCADE,
        related_name='progress_step_records', db_index=True,
        verbose_name='Paso del onboarding',
        help_text='Paso cuyo progreso trackea este registro '
                  '(Odoo step_id).',
    )
    # Odoo company_id (onboarding_progress_step.py:19, ondelete cascade).
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, null=True, blank=True,
        related_name='onboarding_progress_step_records',
        verbose_name='Empresa (si el paso es per-company)',
    )
    # Odoo step_state (onboarding_progress_step.py:14-15).
    step_state = fields.Selection(
        max_length=16, choices=ONBOARDING_PROGRESS_STATES,
        default=STATE_NOT_DONE, verbose_name='Estado de progreso del paso',
    )

    # Soporte del UniqueIndex con COALESCE — mismo patrón que
    # ``OnboardingProgress.company_key`` (ver su docstring: H-API-281,
    # MariaDB sin índices por expresión). Odoo:
    # ``_company_uniq = models.UniqueIndex('(step_id, COALESCE(company_id,
    # 0))')`` (línea 21).
    company_key = models.GeneratedField(
        expression=Coalesce('company_id', models.Value(0)),
        output_field=models.BigIntegerField(),
        db_persist=True,
    )

    class Meta:
        db_table = 'onboarding_progress_step'
        verbose_name = 'Progreso de paso de onboarding'
        verbose_name_plural = 'Progresos de paso de onboarding'
        constraints = [
            models.UniqueConstraint(
                fields=['step', 'company_key'],
                name='onboarding_progress_step_company_uniq',
            ),
        ]

    def __str__(self):
        # Odoo ``_rec_name = 'step_id'``.
        return str(self.step_id)

    def action_consolidate_just_done(self):
        """``action_consolidate_just_done`` (línea 23-26).

        Devuelve ``True`` si este registro estaba ``just_done`` y pasó a
        ``done`` en esta llamada (equivalente a la verdad del recordset
        ``was_just_done`` de la referencia).
        """
        if self.step_state != STATE_JUST_DONE:
            return False
        self.step_state = STATE_DONE
        self.save(update_fields=['step_state'])
        return True

    def action_set_just_done(self):
        """``action_set_just_done`` (línea 28-31).

        Devuelve ``True`` si este registro estaba ``not_done`` y pasó a
        ``just_done`` en esta llamada.
        """
        if self.step_state != STATE_NOT_DONE:
            return False
        self.step_state = STATE_JUST_DONE
        self.save(update_fields=['step_state'])
        return True

    @classmethod
    def consolidate_just_done_queryset(cls, queryset):
        """Variante de lote de ``action_consolidate_just_done`` sobre
        ``queryset`` (ver docstring del módulo: Odoo opera en recordset).

        Devuelve el número de filas consolidadas ``just_done`` -> ``done``.
        """
        just_done_ids = list(
            queryset.filter(step_state=STATE_JUST_DONE)
            .values_list('pk', flat=True),
        )
        if just_done_ids:
            cls.objects.filter(pk__in=just_done_ids).update(
                step_state=STATE_DONE)
        return len(just_done_ids)
