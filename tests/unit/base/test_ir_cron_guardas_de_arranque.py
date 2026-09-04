"""``_check_version`` y ``_check_modules_state`` — las dos guardas del planificador.

Ninguna de las dos tenía un caso: medido antes de escribir este archivo,
``grep -rln "_check_modules_state\\|_check_version" tests/`` daba **0**. Son las
que deciden si el planificador arranca, así que su verde importaba y nadie lo
había medido.

``_check_modules_state`` tiene además una rama que hoy es **inalcanzable**: su
consulta busca ``state LIKE 'to %'`` y ``IrModule.STATES`` declara tres estados,
ninguno con ese prefijo (divergencia declarada en el propio método — el
instalador de la fuente no existe aquí). Este archivo la ejercita **inyectando
la fila que el árbol no sabe producir**, que es la única forma de saber si la
lógica del umbral funciona o es decorado.

Referencia: ``odoo19c: odoo/addons/base/models/ir_cron.py:239-281``.
"""
from datetime import timedelta

import pytest
from django.db.migrations import executor as executor_module
from django.utils import timezone

from addons.base.models.ir_actions import IrActionsServer
from addons.base.models.ir_cron import (
    MAX_FAIL_TIME,
    BadModuleState,
    BadVersion,
    IrCron,
)
from addons.base.models.ir_module import IrModule


pytestmark = pytest.mark.django_db


def _cron(nextcall_delta=timedelta(minutes=-5)):
    action = IrActionsServer.objects.create(
        name='Guarda', model_name='base.SystemParameter',
        method_name='noop_test', state='code', path=None)
    return IrCron.objects.create(
        ir_actions_server=action,
        nextcall=timezone.now() + nextcall_delta,
        priority=5, active=True)


def _module_in_transit():
    """La fila que este árbol NO sabe producir.

    ``_derive_state`` (``update_module_list``) es función pura de
    ``(manifest, INSTALLED_APPS)`` y sólo devuelve tres valores. Se escribe a
    mano —Django no valida ``choices`` en ``save()``— porque sin ella la rama
    del umbral no se puede medir.
    """
    return IrModule.objects.create(name='addon_en_transito', state='to install')


# --- _check_modules_state ---------------------------------------------------

def test_without_modules_in_transit_the_guard_lets_the_scheduler_through():
    """El caso por construcción: ninguna fila lleva un estado ``'to '``."""
    assert IrModule.objects.filter(state__startswith='to ').count() == 0
    IrCron._check_modules_state(jobs=[])


def test_a_module_in_transit_with_no_jobs_blocks():
    _module_in_transit()
    with pytest.raises(BadModuleState):
        IrCron._check_modules_state(jobs=[])


def test_a_module_in_transit_with_recent_jobs_blocks():
    _module_in_transit()
    with pytest.raises(BadModuleState):
        IrCron._check_modules_state(jobs=[_cron()])


def test_jobs_stuck_past_the_threshold_stop_blocking():
    """La rama del umbral: la fuente deja de bloquear y resetea el estado.

    Aquí no hay ``reset_modules_state`` que llamar —ver la divergencia
    declarada en el método—, así que el porte llega hasta *dejar de bloquear*.

    **Este caso NO discrimina por sí solo.** Medido con la guarda anulada
    —el cuerpo del método sustituido por un ``return`` seco— sigue **verde**,
    porque afirma que algo *no* ocurre. Su valor está en el trío: con los dos
    anteriores en rojo bajo esa misma anulación, el conjunto separa «el umbral
    decide» de «nunca se bloquea». Leerlo aislado sería el sub-patrón D de
    ``metrica-decide-la-conclusion.md``.
    """
    _module_in_transit()
    stale = _cron(nextcall_delta=-(MAX_FAIL_TIME + timedelta(minutes=1)))
    IrCron._check_modules_state(jobs=[stale])


# --- _check_version ---------------------------------------------------------

def test_with_the_schema_up_to_date_the_version_guard_lets_it_through():
    IrCron._check_version()


def test_a_pending_migration_is_this_tree_version_mismatch(monkeypatch):
    """≙ ``latest_version != BASE_VERSION`` de la fuente.

    El equivalente exacto de «el código espera un schema que la base no
    tiene» es una migración sin aplicar, y eso lo sabe Django.
    """
    monkeypatch.setattr(
        executor_module.MigrationExecutor, 'migration_plan',
        lambda self, targets, clean_start=False: [('base', '0002_pendiente')])
    with pytest.raises(BadVersion):
        IrCron._check_version()
