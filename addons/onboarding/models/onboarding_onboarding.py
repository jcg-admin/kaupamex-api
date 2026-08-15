"""``onboarding.onboarding`` — addon ``onboarding``.

Adaptación fiel de Odoo onboarding/models/onboarding_onboarding.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Un panel de onboarding: un conjunto ordenado de pasos
(``onboarding.onboarding.step``) con progreso trackeado por
``onboarding.progress`` (globalmente o per-compañía, según
``is_per_company``).

**GAP — sin panel web (documentado, no relleno).** Este addon porta el
MODELO de progreso; NO porta ``views/onboarding_templates.xml``,
``views/onboarding_views.xml``, ``views/onboarding_menus.xml`` ni
``static/src/**`` (componentes OWL del panel embebido en el backend web de
Odoo) — no hay a qué adaptar un cliente web OWL en un backend Django REST.
Ver ``__manifest__.py``.
"""
from django.db import models

import fields

from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.onboarding.models.onboarding_progress import (
    STATE_NOT_DONE,
    OnboardingProgress,
    _resolve_company_id,
)
from addons.onboarding.models.onboarding_progress_step import (
    OnboardingProgressStep,
)


class OnboardingOnboarding(TimeStampedModel):
    """``onboarding.onboarding`` — panel de onboarding."""

    # Odoo name (onboarding_onboarding.py:13, translate).
    name = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Nombre',
    )
    # Odoo route_name (línea 14-15, required). "One word identifier used to
    # define the onboarding panel's route: /onboarding/{route_name}" — sin
    # panel web, no hay ruta HTTP que servir; el campo se conserva como
    # identificador estable del onboarding (mismo rol que un slug).
    route_name = fields.Char(
        max_length=64, unique=True, verbose_name='Identificador de una '
        'palabra',
        help_text='Identificador estable del onboarding (Odoo route_name; '
                  'sin panel web, no define una ruta HTTP aquí).',
    )
    # Odoo step_ids (línea 16) — M2M declarado UNA sola vez, del lado
    # Onboarding->Step; ``related_name`` da el accesor inverso equivalente a
    # ``onboarding_ids`` de la referencia (ver docstring de
    # ``OnboardingOnboardingStep``: Odoo lo declara en ambos modelos, pero
    # describe una única relación bidireccional).
    steps = fields.Many2many(
        'onboarding.OnboardingOnboardingStep', related_name='onboardings',
        blank=True, verbose_name='Pasos del onboarding',
    )
    # Odoo text_completed (línea 18-20).
    text_completed = fields.Char(
        max_length=255, blank=True,
        default='Nice work! Your configuration is done.',
        verbose_name='Mensaje al completar',
        help_text='Texto mostrado cuando el onboarding se completa.',
    )
    # Odoo panel_close_action_name (línea 25-26).
    panel_close_action_name = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Acción de cierre',
        help_text='Nombre de la acción de modelo a ejecutar al cerrar el '
                  'panel.',
    )
    # Odoo sequence (línea 39, default 10).
    sequence = fields.Integer(default=10, verbose_name='Secuencia')

    class Meta:
        db_table = 'onboarding_onboarding'
        # Odoo ``_order = 'sequence asc, id desc'``.
        ordering = ['sequence', '-id']
        verbose_name = 'Onboarding'
        verbose_name_plural = 'Onboardings'

    def __str__(self):
        return self.name or self.route_name

    # -- Cómputos (Odoo @api.depends, NO store=True) ------------------------

    @property
    def is_per_company(self):
        """``_compute_is_per_company`` (línea 45-54).

        Una vez per-company, se mantiene per-company aunque se desvinculen
        los steps per-company — evita tener que fusionar registros de
        progreso ya existentes (comentario verbatim de la fuente).
        """
        if self.progress_records.filter(company__isnull=False).exists():
            return True
        return self.steps.filter(is_per_company=True).exists()

    def get_current_progress(self, company=None):
        """``_compute_current_progress`` (línea 56-69), mitad
        ``current_progress_id``. ``company`` explícito o compañía ambiente.

        Nota de fidelidad: la referencia filtra
        ``company_id in {False, self.env.company.id}`` sobre un recordset,
        que en teoría podría traer 2 filas (una global + una de la compañía
        actual) si el índice único con COALESCE no lo hubiera impedido para
        el MISMO valor — no es el caso aquí (COALESCE distingue NULL de un
        id real), pero SÍ pueden coexistir una fila global y una de compañía
        para el mismo onboarding (COALESCE da 0 vs N, valores distintos). Se
        prioriza la fila de la compañía activa sobre la global, que es la
        lectura más razonable de "el progreso PARA esta compañía".
        """
        context_company_id = _resolve_company_id(company)
        candidates = self.progress_records.filter(
            models.Q(company__isnull=True)
            | models.Q(company_id=context_company_id),
        )
        if context_company_id is not None:
            specific = candidates.filter(company_id=context_company_id).first()
            if specific is not None:
                return specific
        return candidates.filter(company__isnull=True).first()

    @property
    def current_progress(self):
        """≙ ``current_progress_id`` / ``_compute_current_progress``
        (``:28-29``, ``:58-69``)."""
        return self.get_current_progress()

    @property
    def current_onboarding_state(self):
        progress = self.get_current_progress()
        return progress.onboarding_state if progress else STATE_NOT_DONE

    @property
    def is_current_progress_closed(self):
        """``is_onboarding_closed`` (compute, línea 33) para la compañía
        ambiente. Nombre distinto del campo homónimo en ``OnboardingProgress``
        para no confundir el compute con la columna almacenada."""
        progress = self.get_current_progress()
        return bool(progress and progress.is_onboarding_closed)

    # -- Mutaciones -----------------------------------------------------

    def set_steps(self, steps):
        """Reemplaza los pasos vinculados y recalcula el progreso si el
        conjunto cambió.

        Sustituye la porción de ``write()`` (línea 71-77) que en Odoo se
        dispara al escribir ``step_ids`` — Django no enruta ``.set()`` de un
        M2M a través de ``save()``, así que se expone este método explícito
        con la MISMA semántica (recalcular ``progress_step_ids`` de las
        progress records si el conjunto de pasos cambió).
        """
        previous_ids = set(self.steps.values_list('pk', flat=True))
        self.steps.set(steps)
        new_ids = {getattr(s, 'pk', s) for s in steps}
        if previous_ids != new_ids:
            for progress in self.progress_records.all():
                progress.recompute_progress_step_ids()

    def action_close(self):
        """Odoo línea 79-81."""
        progress = self.get_current_progress()
        if progress is not None:
            progress.action_close()

    @classmethod
    def action_close_panel_by_id(cls, onboarding_id):
        """``action_close_panel(xmlid)`` (línea 83-90).

        GAP de xmlid (documentado, no relleno) — ver el mismo gap descrito
        en ``OnboardingOnboardingStep.action_validate_step_by_id``. Se recibe
        el ``pk`` en vez del xmlid; "quietly do nothing" si no existe, igual
        que la fuente.
        """
        onboarding = cls.objects.filter(pk=onboarding_id).first()
        if onboarding is not None:
            onboarding.action_close()

    def action_refresh_progress_ids(self):
        """``action_refresh_progress_ids`` (línea 92-102).

        Re-inicializa el progreso tras volverse per-company (invocado
        cuando ``is_per_company`` de un step vinculado cambia, o se le
        vincula un step per-company).
        """
        if self.is_per_company:
            global_progress = self.progress_records.filter(company__isnull=True)
            if global_progress.exists():
                global_progress.delete()
                self._create_progress()

    def action_toggle_visibility(self):
        """Odoo línea 104-105."""
        progress = self.get_current_progress()
        if progress is not None:
            progress.action_toggle_visibility()

    def search_or_create_progress(self, company=None):
        """``_search_or_create_progress`` (línea 107-111)."""
        progress = self.get_current_progress(company=company)
        if progress is None:
            progress = self._create_progress(company=company)
        return progress

    def _create_progress(self, company=None):
        """``_create_progress`` (línea 113-123)."""
        context_company_id = _resolve_company_id(company)
        progress_company_id = context_company_id if self.is_per_company else None
        linked_step_progress = OnboardingProgressStep.objects.filter(
            step__in=self.steps.all(),
        ).filter(
            models.Q(company__isnull=True)
            | models.Q(company_id=context_company_id),
        )
        progress = OnboardingProgress.objects.create(
            onboarding=self, company_id=progress_company_id,
        )
        progress.progress_steps.set(linked_step_progress)
        return progress

    def prepare_rendering_values(self):
        """``_prepare_rendering_values`` (línea 125-136).

        Se porta el CÁLCULO (contrato de datos del panel), no el renderizado
        HTML — la plantilla QWeb del panel (``views/onboarding_templates.
        xml``) no se porta (sin cliente web, ver el manifest). Un futuro
        endpoint DRF que sirva el estado del panel puede serializar este
        dict directamente.
        """
        progress = self.get_current_progress()
        onboarding_states_values = (
            progress.get_and_update_onboarding_state() if progress
            else {'onboarding_state': STATE_NOT_DONE}
        )
        return {
            'close_method': self.panel_close_action_name,
            'close_model': 'onboarding.OnboardingOnboarding',
            'steps': list(self.steps.all()),
            'state': onboarding_states_values,
            'text_completed': self.text_completed,
        }
