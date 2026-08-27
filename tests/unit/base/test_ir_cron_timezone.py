"""``_reschedule_later`` suma el intervalo en la zona del usuario, no en UTC.

Porta la conversion de ``odoo19c: odoo/addons/base/models/ir_cron.py:641-650``
(LGPL-3), cuyo comentario declara la razon entera del paso::

    Use the timezone of the user when adding the interval. When adding a
    day or more, the user may want to keep the same hour each day.
    The interval won't be fixed, but the hour will stay the same,
    even when changing DST.

Antes de este pase la suma era en UTC y el docstring lo declaraba como
divergencia con su sucesor citado (tarea #43). Esta suite lo cierra.

Verificado contra la biblioteca ANTES de escribir los casos::

    zoneinfo tiene America/Mexico_City: True
    pytz: AUSENTE          -> la fuente usa pytz; aqui zoneinfo, declarado

El control que puede fallar — y la fecha esta elegida, no tomada al azar
------------------------------------------------------------------------

Los dos casos de horario de verano usan **America/New_York**, cuya transicion
esta viva: el segundo domingo de marzo la zona pasa de UTC-5 a UTC-4.
``America/Mexico_City`` NO sirve para este control — Mexico abolio el horario
de verano en 2022 y su offset es constante, asi que un caso sobre esa zona
pasaria con la conversion **y** sin ella. Es el sub-patron D de
``metrica-decide-la-conclusion.md``: un verde que no discrimina.

Medido: revirtiendo la conversion a la suma en UTC —``_add_interval(nextcall,
...)`` sin los dos ``astimezone``— esta suite pasa de **7 passed** a
**1 failed, 6 passed**, y cae ``test_the_hour_survives_the_spring_transition``
con ``assert (10, 0) == (9, 0)``, que es literalmente el defecto que el
comentario de la fuente describe.

**Uno, no dos** — y la diferencia importa. La primera version de esta suite
predijo dos y midio uno; el caso de otono pasaba **sin tocar nada**, porque su
``nextcall`` estaba en el futuro y el bucle de ``_reschedule_later`` no entra.
Se reescribio para medir la aritmetica directamente. Predecir el resultado de
un control y no correrlo habria dejado aqui una cifra falsa sobre un caso que
no medía nada — el sub-patron D dentro del texto que lo explica.

Y hay una segunda leccion en el mismo control: la primera version tampoco
hacia ``refresh_from_db()``, asi que leia el ``tzinfo`` que el fixture puso en
memoria en vez del UTC que devuelve la base. Con eso la aritmetica de reloj de
pared conservaba la hora **con la conversion y sin ella**: 7 passed en los dos
sentidos. El runner lee el job de la base; el caso tiene que leerlo igual.
"""
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from addons.base.models import IrActionsServer, IrCron, ResPartner, ResUsers
from addons.base.models.ir_cron import _add_interval, _resolve_tz
from orm.environments import context_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

NEW_YORK = 'America/New_York'


@pytest.fixture
def action():
    return IrActionsServer.objects.create(
        name='Tarea con zona', state='code',
        model_name='base.SystemParameter', method_name='noop_test')


def _user_with_tz(tz):
    partner = ResPartner.objects.create(name='Operador', tz=tz)
    return ResUsers.objects.create(
        login=f'op-{tz or "sin"}-{partner.pk}', partner=partner)


def _daily_cron(action, user, nextcall):
    return IrCron.objects.create(
        ir_actions_server=action, user=user, interval_number=1,
        interval_type='days', nextcall=nextcall, active=True)


# --------------------------------------------------------------------------
# _resolve_tz — ≙ Environment.tz, con su mismo orden de precedencia
# --------------------------------------------------------------------------

def test_the_user_timezone_wins_when_the_context_is_silent(db):
    user = _user_with_tz(NEW_YORK)
    assert _resolve_tz(user) == ZoneInfo(NEW_YORK)


def test_the_context_beats_the_user(db):
    """≙ ``self.context.get('tz') or self.user.tz`` — el contexto primero."""
    user = _user_with_tz(NEW_YORK)
    with context_scope(tz='Europe/Madrid'):
        assert _resolve_tz(user) == ZoneInfo('Europe/Madrid')


def test_no_timezone_anywhere_falls_back_to_utc(db):
    assert _resolve_tz(_user_with_tz('')) == dt_timezone.utc
    assert _resolve_tz(None) == dt_timezone.utc


def test_an_invalid_timezone_degrades_instead_of_aborting(db):
    """La fuente lo registra en DEBUG y sigue; un cron no muere por eso."""
    assert _resolve_tz(_user_with_tz('Marte/Olympus_Mons')) == dt_timezone.utc


# --------------------------------------------------------------------------
# El cambio de horario — lo unico que la conversion existe para preservar
# --------------------------------------------------------------------------

def test_the_hour_survives_the_spring_transition(action, db):
    """Un cron diario a las 09:00 sigue a las 09:00 al pasar a horario de verano.

    2026-03-08 es el segundo domingo de marzo: America/New_York pasa de
    UTC-5 a UTC-4 a las 02:00 locales. Las 09:00 del dia 7 son las 14:00 UTC;
    las del dia 8, las 13:00 UTC. Sumar en UTC daria 14:00 UTC = 10:00 local.
    """
    user = _user_with_tz(NEW_YORK)
    before = datetime(2026, 3, 7, 9, 0, tzinfo=ZoneInfo(NEW_YORK))
    cron = _daily_cron(action, user, before)
    cron.refresh_from_db()       # como lo lee el runner: UTC, no la tz del fixture
    cron._reschedule_later()

    local = cron.nextcall.astimezone(ZoneInfo(NEW_YORK))
    assert (local.hour, local.minute) == (9, 0)
    assert local.date() > before.date()


def test_the_hour_survives_the_autumn_transition():
    """El sentido contrario —de UTC-4 a UTC-5— medido en la aritmetica.

    NO pasa por ``_reschedule_later``, y la razon es que ese metodo **no lo
    puede decidir**: su bucle avanza hasta superar ``ahora``, asi que una
    transicion de otono en el pasado se cruza junto con la de primavera
    siguiente y los dos desplazamientos se cancelan — un verde que no
    discrimina. Una transicion de otono en el futuro es peor: el bucle no
    entra y la asercion no toca nada.

    Aqui se mide la unidad que la conversion protege: sumar un dia sobre un
    datetime **en la zona** conserva la hora de pared; sumarlo en UTC no.
    2025-11-02 es la transicion, y esta a un solo paso de 2025-11-01.
    """
    zone = ZoneInfo(NEW_YORK)
    before = datetime(2025, 11, 1, 9, 0, tzinfo=zone)

    in_zone = _add_interval(before.astimezone(zone), 1, 'days')
    assert in_zone.astimezone(zone).hour == 9

    in_utc = _add_interval(before.astimezone(dt_timezone.utc), 1, 'days')
    assert in_utc.astimezone(zone).hour == 8      # el defecto, medido


def test_an_interval_in_hours_is_a_fixed_amount(action, db):
    """El comentario de la fuente dice *"a day or more"*: en horas no aplica.

    Un intervalo horario es una cantidad fija de tiempo; convertir y volver
    no lo cambia, y este caso lo fija para que un refactor no introduzca un
    desplazamiento donde la fuente no lo tiene.
    """
    user = _user_with_tz(NEW_YORK)
    before = timezone.now() - timedelta(hours=3)
    cron = IrCron.objects.create(
        ir_actions_server=action, user=user, interval_number=2,
        interval_type='hours', nextcall=before, active=True)
    cron._reschedule_later()
    delta = cron.nextcall - before
    assert delta.total_seconds() % 7200 == 0
    assert cron.nextcall > timezone.now()
