"""``onboarding.onboarding.step`` — addon ``onboarding``.

Adaptación fiel de Odoo onboarding/models/onboarding_onboarding_step.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Un paso de un panel de onboarding: título, texto del botón, ícono/texto de
completado, y la acción que abre el paso.

**GAP — sin panel web (documentado, no relleno).** ``_get_placeholder_
filename`` (línea 107-111 de la referencia) engancha el campo ``step_image``
al mecanismo de imagen-de-relleno (``ir.binary``/``_find_record`` de Odoo).
``addons.base.models.ir_binary.IrBinary`` ya porta el placeholder GENÉRICO
(``get_placeholder_path``/``placeholder``), pero NO expone un hook por-campo
como el override de Odoo — es infraestructura de servir binarios (misma
frontera que el resto del panel web, fuera de scope de este addon; ver el
manifest). No se inventa el hook: se documenta el gap.
"""
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models

import fields

from addons.onboarding.models.onboarding_progress import (
    STATE_NOT_DONE,
    _resolve_company_id,
)
from addons.onboarding.models.onboarding_progress_step import (
    OnboardingProgressStep,
)


class OnboardingOnboardingStep(models.Model):
    """``onboarding.onboarding.step`` — paso de un panel de onboarding.

    NO hereda ``TimeStampedModel``: Odoo declara ``onboarding.onboarding.step``
    como modelo propio (sin mixin), y a diferencia de ``crm.team``/
    ``hr.department`` (que sí llevan ``create_date``/``write_date`` fieles a
    la referencia), aquí ningún campo ni método de la fuente lee esas
    columnas — se mantiene fiel al modelo real en vez de aplicar el mixin por
    inercia de convención de proyecto.
    """

    # Odoo onboarding_ids (onboarding_onboarding_step.py:15) — declarado del
    # LADO de ``OnboardingOnboarding.steps`` (ver su docstring): Odoo declara
    # el M2M en AMBOS modelos (comodelos recíprocos), pero eso describe UNA
    # sola relación bidireccional, no dos tablas — el accesor inverso
    # ``onboardings`` viene del ``related_name`` de ``steps`` allá.

    # Odoo title (onboarding_onboarding_step.py:17, translate).
    title = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Título',
    )
    # Odoo description (línea 18, translate).
    description = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Descripción',
    )
    # Odoo button_text (línea 19-21, required, default "Let's do it").
    button_text = fields.Char(
        max_length=255, default="Let's do it", verbose_name='Texto del botón',
        help_text='Texto del botón que arranca este paso '
                  '(Odoo button_text).',
    )
    # Odoo done_icon (línea 22, default 'fa-star').
    done_icon = fields.Char(
        max_length=64, default='fa-star',
        verbose_name='Ícono Font Awesome al completar',
    )
    # Odoo done_text (línea 23-24, default 'Step Completed!').
    done_text = fields.Char(
        max_length=255, default='Step Completed!',
        verbose_name='Texto al completar el paso',
    )
    # Odoo step_image / step_image_filename (línea 25-26).
    step_image = fields.Binary(
        null=True, blank=True, verbose_name='Imagen del paso',
    )
    step_image_filename = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Nombre de archivo de la imagen',
    )
    # Odoo step_image_alt (línea 27-29, default 'Onboarding Step Image').
    step_image_alt = fields.Char(
        max_length=255, default='Onboarding Step Image',
        verbose_name='Texto alternativo de la imagen del paso',
    )
    # Odoo panel_step_open_action_name (línea 30-33). NO required a nivel de
    # campo en la referencia — el requisito es CONDICIONAL (sólo si el paso
    # está vinculado a un onboarding), verificado en ``clean()`` (ver abajo,
    # adaptación de ``check_step_on_onboarding_has_action``).
    panel_step_open_action_name = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Acción de apertura',
        help_text='Nombre de la acción de modelo a ejecutar al abrir el '
                  'paso, p. ej. action_open_onboarding_1_step_1.',
    )
    # Odoo is_per_company (línea 44, default True).
    is_per_company = fields.Boolean(
        default=True, verbose_name='¿Es per-company?',
    )
    # Odoo sequence (línea 45, default 10).
    sequence = fields.Integer(default=10, verbose_name='Secuencia')

    class Meta:
        db_table = 'onboarding_onboarding_step'
        # Odoo ``_order = 'sequence asc, id asc'``.
        ordering = ['sequence', 'id']
        verbose_name = 'Paso de onboarding'
        verbose_name_plural = 'Pasos de onboarding'

    def __str__(self):
        # Odoo ``_rec_name = 'title'``.
        return self.title or f'Step {self.pk}'

    def clean(self):
        """``check_step_on_onboarding_has_action`` (línea 65-72).

        En la referencia es un ``@api.constrains('onboarding_ids')`` (se
        dispara al vincular). Aquí, ``onboardings`` (M2M inverso) requiere PK
        existente, así que sólo se evalúa si el registro ya está guardado.
        """
        super().clean()
        if self.pk and self.onboardings.exists() and not self.panel_step_open_action_name:
            raise ValidationError(
                'Se requiere una "Acción de apertura" para vincular este '
                'paso a un panel de onboarding: %s' % (self.title or self.pk)
            )

    def save(self, *args, **kwargs):
        """Adaptación de ``write()`` (línea 74-92).

        Intercepta el cambio de ``is_per_company`` (campo escalar: SÍ pasa
        por ``save()``). El disparador de ``onboarding_ids`` (M2M) de la
        referencia NO tiene equivalente aquí — Django no enruta `.add()`/
        `.set()` de un M2M a través de ``save()``. Ver ``link_onboarding()``
        para ese caso.
        """
        is_per_company_changed = False
        if self.pk:
            previous_value = type(self).objects.filter(
                pk=self.pk,
            ).values_list('is_per_company', flat=True).first()
            is_per_company_changed = (
                previous_value is not None
                and previous_value != self.is_per_company
            )
        super().save(*args, **kwargs)
        if is_per_company_changed:
            # Odoo: "Progress is reset (to be done per-company or, for
            # steps, to have a single record)".
            self.progress_step_records.all().delete()
        for onboarding in self.onboardings.all():
            onboarding.action_refresh_progress_ids()

    def link_onboarding(self, onboarding):
        """Vincula ``onboarding`` a este paso.

        Sustituye la porción de ``write()`` que en Odoo se dispara al
        escribir ``onboarding_ids`` (línea 89-90: "if self.onboarding_ids -
        already_linked_onboardings: ...progress_ids._recompute_progress_
        step_ids()") — aquí explícita porque Django no intercepta cambios de
        M2M en ``save()``.
        """
        already_linked = self.onboardings.filter(pk=onboarding.pk).exists()
        self.onboardings.add(onboarding)
        if not already_linked:
            for progress in onboarding.progress_records.all():
                progress.recompute_progress_step_ids()

    def current_progress_step(self, company=None):
        """``_compute_current_progress`` (línea 47-63), sólo la mitad del
        step (``current_progress_step_id``); ``current_step_state`` está
        abajo. ``company`` explícito o compañía ambiente (ver
        ``onboarding_progress._resolve_company_id``)."""
        if not self.pk:
            return None
        context_company_id = _resolve_company_id(company)
        return self.progress_step_records.filter(
            models.Q(company__isnull=True)
            | models.Q(company_id=context_company_id),
        ).first()

    def current_step_state(self, company=None):
        """``current_step_state`` — mitad del compute línea 47-63."""
        progress_step = self.current_progress_step(company=company)
        return progress_step.step_state if progress_step else STATE_NOT_DONE

    def action_set_just_done(self, company=None):
        """``action_set_just_done`` (línea 94-98).

        Devuelve ``self`` si el estado del progreso pasó de ``not_done`` a
        ``just_done`` EN ESTA llamada (equivalente de verdad al recordset no
        vacío que la referencia devuelve), o ``None`` si ya estaba
        done/just_done.
        """
        progress_step = self.current_progress_step(company=company)
        if progress_step is None:
            progress_step = self._create_progress_step(company=company)
        changed = progress_step.action_set_just_done()
        return self if changed else None

    @classmethod
    def action_validate_step_by_id(cls, step_id, company=None):
        """Adaptación de ``action_validate_step(xml_id)`` (línea 100-105).

        GAP de xmlid (documentado, no relleno): sin un cargador de datos
        declarativos que pueble ``ir.model.data`` en este monolito (mismo gap
        que ``addons.base.models.ir_binary`` documenta para ``_find_record``
        por xmlid — "la resolución por xmlid entra cuando haya filas que
        resolver, no antes"), no hay ``env.ref(xml_id)`` que resolver. Se
        recibe el ``pk`` directamente en su lugar.
        """
        step = cls.objects.filter(pk=step_id).first()
        if step is None:
            return 'NOT_FOUND'
        return 'JUST_DONE' if step.action_set_just_done(company=company) else 'WAS_DONE'

    def _create_progress_step(self, company=None):
        """``_create_progress_steps`` (línea 113-133), adaptado a un solo
        step (la referencia opera en recordset; ver docstring del módulo
        hermano ``onboarding_progress_step.py``).

        ``apps.get_model`` (llamada, no ``Import``/``ImportFrom``) en vez de
        importar ``OnboardingProgress`` directo: ese módulo importa
        ``OnboardingProgressStep`` (que ESTE módulo también importa), así que
        un ``from .onboarding_progress import OnboardingProgress`` aquí
        cerraría un ciclo. Mismo recurso que
        ``OnboardingProgress.get_and_update_onboarding_state`` usa para el
        caso inverso — ver su docstring.
        """
        context_company_id = _resolve_company_id(company)
        onboarding_progress_model = apps.get_model(
            'onboarding', 'OnboardingProgress')
        onboarding_progress_records = onboarding_progress_model.objects.filter(
            onboarding__in=self.onboardings.all(),
        ).filter(
            models.Q(company__isnull=True)
            | models.Q(company_id=context_company_id),
        )
        progress_step = OnboardingProgressStep.objects.create(
            step=self,
            company_id=context_company_id if self.is_per_company else None,
        )
        progress_step.progress_records.set(onboarding_progress_records)
        return progress_step
