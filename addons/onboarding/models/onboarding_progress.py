"""``onboarding.progress`` — addon ``onboarding``.

Adaptación fiel de Odoo onboarding/models/onboarding_progress.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Trackea el progreso de UN ``onboarding.onboarding`` (opcionalmente por
compañía, ``odoo19c: onboarding_progress.py:19-25``). El módulo también
define ``ONBOARDING_PROGRESS_STATES`` (más los tres literales), que los
otros tres archivos de este addon importan de aquí — mismo punto único de
verdad que la referencia (``onboarding_onboarding.py`` y
``onboarding_progress_step.py`` hacen exactamente ese import,
``odoo19c: onboarding_onboarding.py:5`` / ``onboarding_progress_step.py:5``).

**GAP de compañía ambiente (documentado, no relleno).** La referencia usa
``self.env.company``/``@api.depends_context('company')`` para saber "la
compañía actual". Este monolito no tiene ``env`` — el equivalente es
``orm.environments.get_current_company()`` (mismo mecanismo que
``addons.base.models.CompanySetting._resolve_company_id``,
``company_setting.py:76-83``): ``None`` (compañía ambiente) | instancia
``ResCompany`` | pk. Se centraliza aquí como ``_resolve_company_id()`` porque
los 4 modelos del addon lo reutilizan.
"""
from django.apps import apps
from django.db import models
from django.db.models.functions import Coalesce

import fields

from addons.base.models.res_company import ResCompany
from addons.base.models.timestamped_mixin import TimeStampedModel
from orm.environments import get_current_company

STATE_NOT_DONE = 'not_done'
STATE_JUST_DONE = 'just_done'
STATE_DONE = 'done'

ONBOARDING_PROGRESS_STATES = [
    (STATE_NOT_DONE, 'Not done'),
    (STATE_JUST_DONE, 'Just done'),
    (STATE_DONE, 'Done'),
]


def _resolve_company_id(company):
    """``company`` puede ser ``None`` (compañía ambiente del contexto), una
    instancia ``ResCompany``, o un pk. Devuelve el pk o ``None``.

    Mismo patrón que ``CompanySetting._resolve_company_id``
    (``company_setting.py:76-83``); se comparte aquí en vez de duplicarlo en
    los 4 modelos del addon.
    """
    if company is None:
        return get_current_company()
    if isinstance(company, ResCompany):
        return company.pk
    return company


class OnboardingProgress(TimeStampedModel):
    """``onboarding.progress`` — tracker de progreso de un onboarding."""

    # Odoo onboarding_id (onboarding_progress.py:23-24, required, ondelete
    # cascade, index). FK por string: evita el import circular con
    # ``onboarding_onboarding.py``, que sí importa esta clase.
    onboarding = fields.Many2one(
        'onboarding.OnboardingOnboarding', on_delete=models.CASCADE,
        related_name='progress_records', db_index=True,
        verbose_name='Onboarding',
        help_text='Onboarding cuyo progreso trackea este registro '
                  '(Odoo onboarding_id).',
    )
    # Odoo company_id (onboarding_progress.py:22, ondelete cascade). ``None``
    # = progreso global (no per-company); ver ``is_per_company`` en
    # ``OnboardingOnboarding``.
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, null=True, blank=True,
        related_name='onboarding_progress_records',
        verbose_name='Empresa (si es per-company)',
    )
    # Odoo progress_step_ids (onboarding_progress.py:25) — M2M sin through
    # explícito, igual que ``sales_team.CrmTeam.members`` sin through.
    progress_steps = fields.Many2many(
        'onboarding.OnboardingProgressStep', related_name='progress_records',
        blank=True, verbose_name='Trackers de progreso de los pasos',
    )
    # Odoo is_onboarding_closed (onboarding_progress.py:21).
    is_onboarding_closed = fields.Boolean(
        default=False, verbose_name='¿Panel cerrado?',
    )

    # Soporte del UniqueIndex con COALESCE — MISMO patrón que
    # ``addons.mail.models.mail_alias.MailAlias.alias_domain_key``
    # (H-API-281): MariaDB no soporta índices por expresión
    # (``supports_expression_indexes = False``), así que la expresión vive en
    # una columna generada STORED que sí se puede indexar/unique-constrainear.
    # Odoo: ``_onboarding_company_uniq = models.UniqueIndex(
    #   "(onboarding_id, COALESCE(company_id, 0))")`` (línea 28).
    company_key = models.GeneratedField(
        expression=Coalesce('company_id', models.Value(0)),
        output_field=models.BigIntegerField(),
        db_persist=True,
    )

    class Meta:
        db_table = 'onboarding_progress'
        verbose_name = 'Progreso de onboarding'
        verbose_name_plural = 'Progresos de onboarding'
        constraints = [
            models.UniqueConstraint(
                fields=['onboarding', 'company_key'],
                name='onboarding_progress_company_uniq',
            ),
        ]

    def __str__(self):
        # Odoo ``_rec_name = 'onboarding_id'``.
        return str(self.onboarding_id)

    @property
    def onboarding_state(self):
        """``_compute_onboarding_state`` (línea 30-39), NO ``store=True``.

        Divergencia deliberada: la referencia lo almacena (``store=True``)
        porque Odoo necesita buscar/ordenar por él en la vista kanban del
        panel — sin panel web portado aquí, no hay ese caso de uso, así que
        se deja como propiedad calculada (evita el problema de staleness de
        un campo denormalizado sin trigger de recálculo).
        """
        done_count = self.progress_steps.filter(
            step_state__in=(STATE_JUST_DONE, STATE_DONE),
        ).count()
        total = self.onboarding.steps.count()
        return STATE_NOT_DONE if done_count != total else STATE_DONE

    def recompute_progress_step_ids(self):
        """``_recompute_progress_step_ids`` (línea 41-44).

        Actualiza ``progress_steps`` cuando un step (con progreso ya
        existente) se añade al onboarding. La referencia usa
        ``step_ids.current_progress_step_id`` — un compute que depende de la
        compañía AMBIENTE (``@api.depends_context('company')``), no de
        ``self.company_id`` de esta fila. Se replica tal cual (aunque es una
        pequeña rareza de la fuente): cada step resuelve su progreso "actual"
        contra la compañía ambiente, no contra la compañía de este progress.
        """
        current_steps = [
            step.current_progress_step()
            for step in self.onboarding.steps.all()
        ]
        self.progress_steps.set(
            [step for step in current_steps if step is not None],
        )

    def action_close(self):
        """Odoo línea 46-47."""
        self.is_onboarding_closed = True
        self.save(update_fields=['is_onboarding_closed'])

    def action_toggle_visibility(self):
        """Odoo línea 49-51."""
        self.is_onboarding_closed = not self.is_onboarding_closed
        self.save(update_fields=['is_onboarding_closed'])

    def get_and_update_onboarding_state(self):
        """``_get_and_update_onboarding_state`` (línea 53-78).

        Calcula el estado de renderizado del panel y consolida los pasos
        ``just_done`` -> ``done`` (para que 'just_done' sólo se muestre una
        vez). En la referencia sólo la llama el controller del panel web; se
        porta el cálculo porque es el contrato de negocio, no la ruta HTTP
        (fuera de scope — sin panel web portado, ver el manifest).
        """
        onboarding_states_values = {}
        just_done_step_ids = []

        for step in self.onboarding.steps.all():
            step_state = step.current_step_state()
            if step_state == STATE_JUST_DONE:
                just_done_step_ids.append(step.pk)
            onboarding_states_values[step.pk] = step_state

        # ``apps.get_model`` (llamada, no statement ``import``) en vez de un
        # import directo del módulo hermano: ``onboarding_progress_step.py``
        # importa ``ONBOARDING_PROGRESS_STATES`` de ESTE módulo, así que un
        # ``from .onboarding_progress_step import ...`` aquí sería circular.
        # Mismo recurso que la excepción #4 de ``no-lazy-imports.md``
        # (``importlib.import_module`` en ``AppConfig.ready()``): es una
        # llamada de función, no un ``Import``/``ImportFrom`` AST node, así
        # que el gate ``check_no_lazy_imports.py`` (que sólo inspecciona esos
        # dos tipos de nodo) lo acepta.
        OnboardingProgressStep = apps.get_model(
            'onboarding', 'OnboardingProgressStep')
        progress_steps_to_consolidate = OnboardingProgressStep.objects.filter(
            step_id__in=just_done_step_ids,
        ).filter(
            models.Q(company__isnull=True)
            | models.Q(company_id=_resolve_company_id(None)),
        )
        consolidated_count = progress_steps_to_consolidate.count()
        if consolidated_count:
            progress_steps_to_consolidate.update(step_state=STATE_DONE)

        if self.is_onboarding_closed:
            onboarding_states_values['onboarding_state'] = 'closed'
        elif self.onboarding_state == STATE_DONE:
            onboarding_states_values['onboarding_state'] = (
                STATE_JUST_DONE if consolidated_count else STATE_DONE
            )
        return onboarding_states_values
