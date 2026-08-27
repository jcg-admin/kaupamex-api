"""``ir.cron.trigger`` / ``ir.cron.progress`` y la mitad del runner que
faltaba — porte completo de ``odoo19c: odoo/addons/base/models/ir_cron.py``.

Antes de este porte el archivo tenia 557 lineas contra 933 de la referencia y
su docstring declaraba como *"deliberadamente NO portado"* casi todo lo que
esta suite ejercita: los dos modelos satelite, el conteo de fallos con sus dos
umbrales, el disparo puntual, la API de progreso y el bucle por lotes.

Verificado contra el motor ANTES de escribir los casos, no de memoria::

    tablas: ['ir_cron_progress', 'ir_cron_trigger']
    columnas nuevas: ['failure_count', 'first_failure_date']
    pg_notify ejecuta: ('',)
    PostgreSQL 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

El control que puede fallar
---------------------------

La guarda que esta suite mide y que se anula para comprobar que discrimina es
**la conjuncion de los dos umbrales de desactivacion**. La fuente exige
``failure_count >= MIN_FAILURE_COUNT_BEFORE_DEACTIVATION`` **y**
``first_failure_date + MIN_DELTA_BEFORE_DEACTIVATION < now`` — un ``and``, no
un ``or``. Cambiarlo por ``or`` desactiva un cron que fallo cinco veces en un
minuto, que es exactamente lo que la fuente evita.

Medido: con el ``and`` sustituido por ``or``, esta suite pasa de **17 passed**
a **1 failed, 16 passed** — cae
``test_five_failures_in_a_minute_do_not_deactivate``, el unico caso cuyo
veredicto depende de cual de los dos operadores se use. Los otros dieciseis
sobreviven y no es defecto: miden los satelites, el disparo y el progreso, que
no tocan esa rama.

El segundo control — el aviso a los workers
--------------------------------------------

``save()`` avisa por el canal solo si ``NOTIFY_CRON_CHANGES`` esta puesta **y**
la escritura toca ``nextcall`` o activa el cron. Sustituyendo las dos
condiciones por un ``transaction.on_commit`` incondicional, la suite pasa de
**21 passed** a **2 failed, 19 passed**: caen exactamente
``test_the_notice_stays_quiet_when_the_switch_is_off`` y
``test_touching_an_unrelated_field_does_not_notify``, que son los dos casos
negativos. El positivo sobrevive, y ahi esta el punto: un aviso incondicional
lo dejaria verde igual, asi que el positivo **solo** no mide la guarda.
"""
import logging
from datetime import timedelta

import pytest
from django.utils import timezone

from addons.base.models import IrActionsServer, IrCron, SystemParameter
from addons.base.models import ir_cron as modulo_ir_cron
from addons.base.models.ir_cron import (CompletionStatus, IrCronProgress,
                                        IrCronTrigger, ListLogHandler,
                                        MIN_FAILURE_COUNT_BEFORE_DEACTIVATION)
from orm.environments import context_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def cron():
    """Un cron listo, con su accion servidor delegada."""
    action = IrActionsServer.objects.create(
        name='Tarea de prueba', state='code',
        model_name='base.SystemParameter', method_name='noop_test')
    return IrCron.objects.create(
        ir_actions_server=action, interval_number=1, interval_type='days',
        nextcall=timezone.now() - timedelta(minutes=1), active=True)


# --------------------------------------------------------------------------
# ir.cron.trigger — el disparo puntual
# --------------------------------------------------------------------------

def test_the_action_of_a_cron_declares_its_usage(cron):
    """≙ ``vals['usage'] = 'ir_cron'`` de ``create`` (``:136-137``)."""
    cron.ir_actions_server.refresh_from_db()
    assert cron.ir_actions_server.usage == 'ir_cron'


def test_the_notice_stays_quiet_when_the_switch_is_off(cron, monkeypatch,
                                                       django_capture_on_commit_callbacks):
    """Sin la variable puesta, escribir un cron NO avisa a los workers.

    Es el control negativo del caso siguiente: si el aviso se emitiera
    siempre, los dos pasarian y ninguno mediria la guarda.
    """
    monkeypatch.setattr(modulo_ir_cron, 'NOTIFY_CRON_CHANGES', False)
    with django_capture_on_commit_callbacks() as callbacks:
        cron.nextcall = timezone.now() + timedelta(hours=1)
        cron.save(update_fields=['nextcall'])
    assert callbacks == []


def test_rescheduling_notifies_the_workers_when_the_switch_is_on(
        cron, monkeypatch, django_capture_on_commit_callbacks):
    """≙ ``('nextcall' in vals or vals.get('active')) and os.getenv(...)``.

    La fuente registra ``_notifydb`` en ``postcommit`` (``:706-707``); el
    equivalente de este ORM es ``transaction.on_commit``. Sin esto, el worker
    que duerme en el canal no se entera de un cron reprogramado hasta su
    siguiente sondeo.
    """
    monkeypatch.setattr(modulo_ir_cron, 'NOTIFY_CRON_CHANGES', True)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        cron.nextcall = timezone.now() + timedelta(hours=1)
        cron.save(update_fields=['nextcall'])
    assert [c.__name__ for c in callbacks] == ['_notifydb']


def test_touching_an_unrelated_field_does_not_notify(
        cron, monkeypatch, django_capture_on_commit_callbacks):
    """La condicion de la fuente nombra ``nextcall`` y ``active``, no todo.

    Escribir solo ``interval_number`` no cambia cuando corre el cron, asi que
    no hay nada que avisar. Este caso es el que distingue la traduccion fiel
    de un ``if NOTIFY_CRON_CHANGES:`` a secas.
    """
    monkeypatch.setattr(modulo_ir_cron, 'NOTIFY_CRON_CHANGES', True)
    with django_capture_on_commit_callbacks() as callbacks:
        cron.interval_number = 7
        cron.save(update_fields=['interval_number'])
    assert callbacks == []


def test_trigger_without_a_moment_means_now(cron):
    triggers = cron._trigger()
    assert len(triggers) == 1
    assert IrCronTrigger.objects.filter(cron=cron).count() == 1


def test_trigger_accepts_a_list_of_moments(cron):
    manana = timezone.now() + timedelta(days=1)
    pasado = timezone.now() + timedelta(days=2)
    cron._trigger([manana, pasado])
    assert IrCronTrigger.objects.filter(cron=cron).count() == 2


def test_an_inactive_cron_drops_expired_triggers(cron):
    """La guarda de ``_trigger_list`` (``:774-776``): un disparo vencido sobre
    un cron apagado no despertaria nada, asi que no se guarda."""
    cron.active = False
    cron.save(update_fields=['active'])
    vencido = timezone.now() - timedelta(hours=1)
    futuro = timezone.now() + timedelta(hours=1)
    cron._trigger([vencido, futuro])
    assert IrCronTrigger.objects.filter(cron=cron).count() == 1


def test_a_trigger_makes_the_cron_ready(cron):
    """La rama ``OR`` de ``_get_ready_sql_condition`` (``:284-293``), que es
    la que este arbol no tenia: sin ella un disparo no despertaba nada."""
    cron.nextcall = timezone.now() + timedelta(days=30)
    cron.save(update_fields=['nextcall'])
    assert cron.pk not in {j.pk for j in IrCron._get_all_ready_jobs()}
    cron._trigger()
    assert cron.pk in {j.pk for j in IrCron._get_all_ready_jobs()}


def test_clear_schedule_only_removes_the_expired_ones(cron):
    """``_clear_schedule`` (``:622-632``) borra los vencidos, no los futuros."""
    cron._trigger([timezone.now() - timedelta(hours=1),
                   timezone.now() + timedelta(hours=1)])
    cron._clear_schedule(cron)
    assert IrCronTrigger.objects.filter(cron=cron).count() == 1


def test_reschedule_asap_leaves_a_trigger_for_now(cron):
    """``_reschedule_asap`` (``:659-669``) — el desenlace ``partially done``."""
    cron._reschedule_asap(cron)
    trigger = IrCronTrigger.objects.get(cron=cron)
    assert trigger.call_at <= timezone.now()


def test_the_collector_only_sweeps_inactive_crons(cron):
    """``_gc_cron_triggers`` (``:906-915``) — su comentario en la fuente dice
    que los activos los limpia ``_clear_schedule`` al arrancar el job."""
    viejo = timezone.now() - timedelta(weeks=2)
    IrCronTrigger.objects.create(cron=cron, call_at=viejo)
    hechos, quedan = IrCronTrigger._gc_cron_triggers()
    assert (hechos, quedan) == (0, False), 'el cron esta ACTIVO: no se barre'

    cron.active = False
    cron.save(update_fields=['active'])
    hechos, quedan = IrCronTrigger._gc_cron_triggers()
    assert hechos == 1
    assert quedan is False


# --------------------------------------------------------------------------
# ir.cron.progress — el avance por lotes
# --------------------------------------------------------------------------

def test_add_progress_advances_the_timeout_counter(cron):
    """El ``timed_out_counter + 1`` de la fuente (``:817-819``): el contador
    se adelanta para que un proceso muerto deje su rastro sin escribirlo."""
    _, progress = cron._add_progress(timed_out_counter=2)
    assert progress.timed_out_counter == 3
    _, without_counter = cron._add_progress()
    assert without_counter.timed_out_counter == 0


def test_commit_progress_outside_a_cron_returns_infinity(cron):
    """La rama de la fuente (``:857-860``) que hace que el mismo metodo sirva
    llamado a mano: sin progreso en contexto, solo comitea."""
    assert IrCron._commit_progress(5) == float('inf')


def test_commit_progress_subtracts_from_what_remains(cron):
    _, progress = cron._add_progress()
    progress.remaining = 10
    progress.save(update_fields=['remaining'])
    with context_scope(ir_cron_progress_id=progress.pk, cron_id=cron.pk):
        IrCron._commit_progress(4)
    progress.refresh_from_db()
    assert (progress.done, progress.remaining) == (4, 6)


def test_commit_progress_accepts_an_explicit_remaining(cron):
    _, progress = cron._add_progress()
    with context_scope(ir_cron_progress_id=progress.pk, cron_id=cron.pk):
        IrCron._commit_progress(3, remaining=99)
    progress.refresh_from_db()
    assert (progress.done, progress.remaining) == (3, 99)


def test_the_progress_collector_sweeps_by_age(cron):
    """``_gc_cron_progress`` (``:929-933``) — la fuente filtra por
    ``create_date``, que aqui es ``created_at``."""
    _, progress = cron._add_progress()
    IrCronProgress.objects.filter(pk=progress.pk).update(
        created_at=timezone.now() - timedelta(weeks=2))
    hechos, quedan = IrCronProgress._gc_cron_progress()
    assert hechos >= 1
    assert quedan is False


# --------------------------------------------------------------------------
# El conteo de fallos y sus DOS umbrales
# --------------------------------------------------------------------------

def test_a_success_resets_the_counter(cron):
    cron.failure_count = 3
    cron.first_failure_date = timezone.now() - timedelta(days=30)
    cron.save(update_fields=['failure_count', 'first_failure_date'])
    cron._update_failure_count(cron, CompletionStatus.FULLY_DONE)
    cron.refresh_from_db()
    assert cron.failure_count == 0
    assert cron.first_failure_date is None
    assert cron.active is True


def test_a_failure_increments_and_stamps_the_first(cron):
    cron._update_failure_count(cron, CompletionStatus.FAILED)
    cron.refresh_from_db()
    assert cron.failure_count == 1
    assert cron.first_failure_date is not None
    assert cron.active is True


def test_five_failures_in_a_minute_do_not_deactivate(cron):
    """El umbral de CONTEO se alcanza; el de TIEMPO no. La fuente exige los
    dos (``:590-593``), y este es el unico caso de la suite cuyo veredicto
    cambia si ese ``and`` se vuelve ``or``."""
    cron.failure_count = MIN_FAILURE_COUNT_BEFORE_DEACTIVATION - 1
    cron.first_failure_date = timezone.now() - timedelta(minutes=1)
    cron.save(update_fields=['failure_count', 'first_failure_date'])
    cron._update_failure_count(cron, CompletionStatus.FAILED)
    cron.refresh_from_db()
    assert cron.active is True, 'el primer fallo es de hace un minuto'
    assert cron.failure_count == MIN_FAILURE_COUNT_BEFORE_DEACTIVATION


def test_five_failures_over_two_weeks_do_deactivate(cron):
    """Los DOS umbrales alcanzados."""
    cron.failure_count = MIN_FAILURE_COUNT_BEFORE_DEACTIVATION - 1
    cron.first_failure_date = timezone.now() - timedelta(weeks=2)
    cron.save(update_fields=['failure_count', 'first_failure_date'])
    cron._update_failure_count(cron, CompletionStatus.FAILED)
    cron.refresh_from_db()
    assert cron.active is False
    assert cron.failure_count == 0, 'se reinicia al desactivar'
    assert cron.first_failure_date is None


# --------------------------------------------------------------------------
# Las piezas de modulo que el porte trajo
# --------------------------------------------------------------------------

def test_the_log_handler_captures_only_inside_the_block():
    """``ListLogHandler`` (``:67-88``) — lo consume
    ``method_direct_trigger`` para saber si el job dejo una excepcion."""
    logger = logging.getLogger('probe.cron')
    with ListLogHandler(logger, logging.ERROR) as capturados:
        logger.error('dentro')
    assert [r.getMessage() for r in capturados] == ['dentro']
    logger.error('fuera')
    assert len(capturados) == 1
