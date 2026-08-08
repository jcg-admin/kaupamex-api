"""Contrato del addon ``onboarding`` (porte de Odoo onboarding/models/**).

Ver la iniciativa de porte en
``docs: gestion/pm/api/iniciativas/<slug-de-esta-iniciativa>`` para el
detalle de la adaptación (M2M explícito de un solo lado, gap de xmlid, gap
del panel web).

**GAP de infraestructura (documentado, no relleno) — addon NO instalado.**
La directiva de esta tarea de porte prohíbe editar
``config/settings/base.py`` (INSTALLED_APPS) y generar migraciones. Sin
``addons.onboarding`` en INSTALLED_APPS, verificado empíricamente
(2026-08-06): las relaciones M2M/reverse de Django (managers, filtros por
nombre de relación) fallan con ``FieldError: Cannot resolve keyword ...`` —
la resolución de relaciones depende de ``apps.get_models()``, que sólo
recorre apps con ``AppConfig`` registrado (el atributo descriptor existe en
la clase igual, pero el manager no puede construir la query). Este módulo
de test instala el addon y crea sus tablas SÓLO para la duración de la
sesión de test, sin tocar ``base.py`` ni crear ``migrations/``:

- ``override_settings(INSTALLED_APPS=...)`` — mecanismo estándar de Django
  para instalar una app temporalmente (internamente llama
  ``apps.set_installed_apps()``/``unset_installed_apps()``).
- ``connection.schema_editor()`` — crea/borra las tablas directamente
  (sin archivo de migración).

Cuando el addon se wireé de verdad (INSTALLED_APPS + migración inicial),
este fixture deja de ser necesario y puede retirarse sin tocar los tests.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from addons.base.models.res_company import ResCompany
from addons.onboarding.models import (
    OnboardingOnboarding,
    OnboardingOnboardingStep,
    OnboardingProgress,
    OnboardingProgressStep,
)
from modules.module import load_manifest
from orm.environments import company_scope

pytestmark = pytest.mark.django_db

# El addon está en ``INSTALLED_APPS`` y tiene su migración
# (``onboarding/0001_initial``), así que las tablas las provee el schema de
# pruebas como las de cualquier otro addon. El andamio original de este
# archivo —``override_settings(INSTALLED_APPS=...)`` + ``schema_editor()``
# para crear y borrar las 6 tablas a mano— existía sólo mientras el addon
# estaba sin cablear, y ahora **rompe**: registrar el mismo app dos veces da
# ``ImproperlyConfigured: Application labels aren't unique``. Ver H-API-297.


def _company(code):
    return ResCompany.objects.create(code=code, name=code)


def _step(title, action='action_open'):
    return OnboardingOnboardingStep.objects.create(
        title=title, panel_step_open_action_name=action,
    )


def _onboarding(route_name, steps=()):
    onboarding = OnboardingOnboarding.objects.create(
        name=route_name, route_name=route_name,
    )
    if steps:
        onboarding.set_steps(steps)
    return onboarding


class TestManifest:
    def test_declares_lgpl3_license_and_measured_depends(self):
        # ``load_manifest`` es el mecanismo canónico del proyecto
        # (``src/modules/module.py``) — ``ast.literal_eval`` sobre el
        # archivo, no ``eval``/import (evita ejecutar código arbitrario).
        manifest = load_manifest('onboarding')
        assert manifest['license'] == 'LGPL-3'
        assert manifest['depends'] == ['base']
        assert manifest['installable'] is True


class TestStepLinkAndReverseRelation:
    def test_set_steps_links_and_reverse_accessor_works(self):
        step1 = _step('Step 1')
        step2 = _step('Step 2')
        onboarding = _onboarding('route_link_1', steps=[step1, step2])
        assert list(
            onboarding.steps.order_by('id').values_list('title', flat=True),
        ) == ['Step 1', 'Step 2']
        assert list(step1.onboardings.values_list('route_name', flat=True)) == [
            'route_link_1',
        ]

    def test_link_onboarding_adds_without_duplicating(self):
        step = _step('Solo step')
        onboarding = _onboarding('route_link_2')
        step.link_onboarding(onboarding)
        step.link_onboarding(onboarding)  # idempotente, no duplica
        assert list(onboarding.steps.values_list('pk', flat=True)) == [step.pk]


class TestCleanRequiresOpeningAction:
    def test_step_without_action_cannot_be_linked(self):
        step = OnboardingOnboardingStep.objects.create(title='Sin accion')
        onboarding = _onboarding('route_clean_1')
        onboarding.set_steps([step])
        with pytest.raises(ValidationError):
            step.full_clean()

    def test_step_with_action_passes_clean(self):
        step = _step('Con accion')
        onboarding = _onboarding('route_clean_2')
        onboarding.set_steps([step])
        step.full_clean()  # no debe lanzar


class TestIsPerCompany:
    def test_defaults_true_because_steps_default_per_company(self):
        # Odoo: is_per_company default True en el step (línea 44).
        step = _step('Step per-company')
        onboarding = _onboarding('route_ipc_1', steps=[step])
        assert onboarding.is_per_company is True

    def test_stays_per_company_after_progress_with_company_exists(self):
        acme = _company('acme-onb-1')
        step = _step('Step ipc 2')
        onboarding = _onboarding('route_ipc_2', steps=[step])
        onboarding.search_or_create_progress(company=acme)
        # Odoo: _compute_is_per_company línea 45-54 — una vez que existe
        # progreso CON compañía, se mantiene per-company aunque los steps
        # dejen de serlo.
        assert onboarding.is_per_company is True


class TestProgressLifecycle:
    def test_search_or_create_progress_is_idempotent(self):
        step = _step('Step progreso 1')
        onboarding = _onboarding('route_progress_1', steps=[step])
        first = onboarding.search_or_create_progress()
        second = onboarding.search_or_create_progress()
        assert first.pk == second.pk

    def test_state_not_done_until_all_steps_just_done(self):
        step1 = _step('Step a')
        step2 = _step('Step b')
        onboarding = _onboarding('route_progress_2', steps=[step1, step2])
        progress = onboarding.search_or_create_progress()
        assert progress.onboarding_state == 'not_done'

        changed = step1.action_set_just_done()
        assert changed is step1
        assert onboarding.get_current_progress().onboarding_state == 'not_done'

        changed2 = step2.action_set_just_done()
        assert changed2 is step2
        progress.refresh_from_db()
        assert progress.onboarding_state == 'done'

    def test_action_set_just_done_returns_none_when_already_done(self):
        step = _step('Step c')
        _onboarding('route_progress_3', steps=[step])
        step.action_set_just_done()
        assert step.action_set_just_done() is None

    def test_empty_onboarding_is_trivially_done(self):
        onboarding = _onboarding('route_progress_4')
        progress = onboarding.search_or_create_progress()
        assert progress.onboarding_state == 'done'


class TestActionValidateStepById:
    """Adaptación de ``action_validate_step(xml_id)`` — recibe pk (gap de
    xmlid documentado en ``OnboardingOnboardingStep``)."""

    def test_not_found_for_unknown_pk(self):
        assert OnboardingOnboardingStep.action_validate_step_by_id(999999) == 'NOT_FOUND'

    def test_just_done_on_first_call_was_done_on_second(self):
        step = _step('Step validate')
        _onboarding('route_validate_1', steps=[step])
        assert OnboardingOnboardingStep.action_validate_step_by_id(step.pk) == 'JUST_DONE'
        assert OnboardingOnboardingStep.action_validate_step_by_id(step.pk) == 'WAS_DONE'


class TestActionClosePanelById:
    """Adaptación de ``action_close_panel(xmlid)`` — recibe pk."""

    def test_closes_current_progress(self):
        step = _step('Step close')
        onboarding = _onboarding('route_close_1', steps=[step])
        onboarding.search_or_create_progress()
        OnboardingOnboarding.action_close_panel_by_id(onboarding.pk)
        assert onboarding.is_current_progress_closed is True

    def test_quietly_does_nothing_for_unknown_pk(self):
        OnboardingOnboarding.action_close_panel_by_id(999999)  # no debe lanzar


class TestCompanyScopedProgress:
    def test_two_companies_get_independent_progress(self):
        acme = _company('acme-onb-2')
        globex = _company('globex-onb-2')
        step = _step('Step multi-company')
        onboarding = _onboarding('route_company_1', steps=[step])
        onboarding.set_steps([step])
        # forzar per-company vinculando un progreso con compañía
        progress_acme = onboarding.search_or_create_progress(company=acme)
        progress_globex = onboarding.search_or_create_progress(company=globex)
        assert progress_acme.pk != progress_globex.pk
        assert onboarding.get_current_progress(company=acme).pk == progress_acme.pk
        assert onboarding.get_current_progress(company=globex).pk == progress_globex.pk

    def test_ambient_company_scope_resolves_current_progress(self):
        acme = _company('acme-onb-3')
        step = _step('Step ambient')
        onboarding = _onboarding('route_company_2', steps=[step])
        onboarding.search_or_create_progress(company=acme)
        with company_scope(acme.pk):
            current = onboarding.get_current_progress()
        assert current is not None
        assert current.company_id == acme.pk


class TestUniqueConstraints:
    def test_duplicate_progress_same_onboarding_same_company_rejected(self):
        acme = _company('acme-onb-4')
        onboarding = _onboarding('route_unique_1')
        OnboardingProgress.objects.create(onboarding=onboarding, company=acme)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                OnboardingProgress.objects.create(onboarding=onboarding, company=acme)

    def test_progress_global_and_per_company_can_coexist(self):
        acme = _company('acme-onb-5')
        onboarding = _onboarding('route_unique_2')
        OnboardingProgress.objects.create(onboarding=onboarding, company=None)
        OnboardingProgress.objects.create(onboarding=onboarding, company=acme)
        assert onboarding.progress_records.count() == 2

    def test_duplicate_progress_step_same_step_same_company_rejected(self):
        acme = _company('acme-onb-6')
        step = _step('Step unique')
        OnboardingProgressStep.objects.create(step=step, company=acme)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                OnboardingProgressStep.objects.create(step=step, company=acme)

    def test_route_name_is_globally_unique(self):
        _onboarding('route_unique_dup')
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                OnboardingOnboarding.objects.create(
                    name='dup', route_name='route_unique_dup',
                )


class TestConsolidateJustDone:
    def test_consolidate_just_done_queryset_flips_only_just_done_rows(self):
        step_a = _step('Consolidate a')
        step_b = _step('Consolidate b')
        row_a = OnboardingProgressStep.objects.create(
            step=step_a, step_state='just_done',
        )
        row_b = OnboardingProgressStep.objects.create(
            step=step_b, step_state='not_done',
        )
        count = OnboardingProgressStep.consolidate_just_done_queryset(
            OnboardingProgressStep.objects.filter(pk__in=[row_a.pk, row_b.pk]),
        )
        row_a.refresh_from_db()
        row_b.refresh_from_db()
        assert count == 1
        assert row_a.step_state == 'done'
        assert row_b.step_state == 'not_done'
