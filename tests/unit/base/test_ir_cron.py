"""Contrato de ``IrCron`` (``ir.cron``) — portación fiel de Odoo,
iniciativa ``adaptar-familias-odoo-monolito-modular`` (SOL-096, H-BASE-01 C-2).

Verifica:

- importable desde el hogar canónico ``addons.base.models``,
- ``db_table``/``app_label`` fieles a Odoo (``ir_cron`` / ``base``),
- campos faithful presentes + defaults de ``interval_number``/
  ``interval_type``/``priority``/``active``,
- ``interval_type`` acepta los 5 choices de Odoo; un valor fuera de catálogo
  es rechazado por ``full_clean()`` (el ``Selection`` del proyecto es
  ``CharField(choices=…)`` — no hay CHECK a nivel de columna, la validación
  es de Django, no de la DB),
- ``_compute_next()`` avanza ``nextcall`` por ``interval_number`` unidades de
  ``interval_type`` para minutes/hours/days/weeks/months (incluyendo el caso
  de overflow de día de mes, sin ``dateutil``, ver docstring de
  ``ir_cron.py``),
- ``user`` nullable con ``on_delete=SET_NULL`` (adaptación deliberada
  respecto al ``user_id`` requerido de Odoo, ver docstring del módulo),
- ``interval_number`` > 0 (CheckConstraint, réplica de
  ``check_strictly_positive_interval`` de Odoo).

Toca DB → django_db.
"""
from datetime import datetime, timezone as dt_timezone

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from addons.base.models import IrActionsServer, IrCron
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _accion(name='Tarea', model_name='orders.Order', method_name='run'):
    """Crea la ``ir.actions.server`` en la que el cron delega su "qué
    ejecutar" (``_inherits``). Antes estos tres campos eran columnas de
    ``IrCron``; desde la portación de la delegación viven aquí."""
    return IrActionsServer.objects.create(
        name=name, model_name=model_name, method_name=method_name,
        state='code',
    )


# --- Importable desde el hogar canónico ------------------------------------

def test_importable_desde_addons_base_models():
    assert IrCron.__module__ == 'addons.base.models.ir_cron'


# --- db_table / app_label fieles a Odoo ------------------------------------

def test_db_table_matches_reference():
    assert IrCron._meta.db_table == 'ir_cron'
    assert IrCron._meta.app_label == 'base'


def test_campos_faithful_presentes():
    field_names = {f.name for f in IrCron._meta.get_fields()}
    for expected in (
        'ir_actions_server', 'interval_number',
        'interval_type', 'nextcall', 'lastcall', 'priority', 'active', 'user',
    ):
        assert expected in field_names, f'falta el campo {expected!r}'
    # name/model_name/method_name YA NO son columnas: se delegan (_inherits).
    for delegado in ('name', 'model_name', 'method_name'):
        assert delegado not in field_names, (
            f'{delegado!r} debe delegarse, no ser columna de ir_cron'
        )
        assert isinstance(getattr(IrCron, delegado), property)


def test_campos_delegados_leen_de_la_accion_servidor():
    accion = _accion(name='Enviar recordatorios', model_name='sale.SaleOrder',
                     method_name='send_reminders')
    cron = IrCron.objects.create(
        ir_actions_server=accion,
        nextcall=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
    )
    assert cron.name == 'Enviar recordatorios'
    assert cron.model_name == 'sale.SaleOrder'
    assert cron.method_name == 'send_reminders'


def test_borrar_la_accion_esta_protegido():
    """Odoo declara el enlace con ``ondelete='restrict'`` (ir_cron.py:108)."""
    accion = _accion()
    IrCron.objects.create(
        ir_actions_server=accion,
        nextcall=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
    )
    with pytest.raises(ProtectedError), transaction.atomic():
        accion.delete()


# --- Creación mínima + defaults ---------------------------------------------

def test_create_minimo_aplica_defaults():
    nextcall = datetime(2026, 8, 1, 3, 0, 0, tzinfo=dt_timezone.utc)
    cron = IrCron.objects.create(
        ir_actions_server=_accion('Enviar recordatorios', 'orders.Order',
                                  'send_reminders'),
        nextcall=nextcall,
    )
    cron.refresh_from_db()

    assert cron.interval_number == 1
    assert cron.interval_type == 'months'
    assert cron.priority == 5
    assert cron.active is True
    assert cron.lastcall is None
    assert cron.user_id is None
    assert cron.nextcall == nextcall


# --- interval_type: choices de Odoo + rechazo de valor inválido -------------

@pytest.mark.parametrize('interval_type', ['minutes', 'hours', 'days', 'weeks', 'months'])
def test_interval_type_accepts_the_five_reference_choices(interval_type):
    cron = IrCron(
        ir_actions_server=_accion('Tarea', 'orders.Order', 'run'),
        nextcall=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
        interval_type=interval_type,
    )
    cron.full_clean()  # no debe lanzar


def test_interval_type_invalido_rechazado_por_full_clean():
    cron = IrCron(
        ir_actions_server=_accion('Tarea', 'orders.Order', 'run'),
        nextcall=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
        interval_type='fortnights',
    )
    with pytest.raises(ValidationError):
        cron.full_clean()


# --- _compute_next(): avance por interval_number x interval_type -----------

def test_compute_next_advances_minutes():
    cron = IrCron(
        interval_number=15, interval_type='minutes',
        nextcall=datetime(2026, 1, 1, 10, 0, 0, tzinfo=dt_timezone.utc),
    )
    assert cron._compute_next() == datetime(2026, 1, 1, 10, 15, 0, tzinfo=dt_timezone.utc)


def test_compute_next_advances_days():
    cron = IrCron(
        interval_number=3, interval_type='days',
        nextcall=datetime(2026, 1, 30, 0, 0, 0, tzinfo=dt_timezone.utc),
    )
    assert cron._compute_next() == datetime(2026, 2, 2, 0, 0, 0, tzinfo=dt_timezone.utc)


def test_compute_next_avanza_months_con_overflow_de_dia():
    # 31 de enero + 1 mes -> el mes destino (febrero) no tiene 31 días;
    # comportamiento observable equivalente a dateutil.relativedelta:
    # clamping al ultimo dia valido del mes (2026 no es bisiesto -> 28).
    cron = IrCron(
        interval_number=1, interval_type='months',
        nextcall=datetime(2026, 1, 31, 9, 0, 0, tzinfo=dt_timezone.utc),
    )
    assert cron._compute_next() == datetime(2026, 2, 28, 9, 0, 0, tzinfo=dt_timezone.utc)


def test_compute_next_advances_weeks():
    cron = IrCron(
        interval_number=2, interval_type='weeks',
        nextcall=datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt_timezone.utc),
    )
    assert cron._compute_next() == datetime(2026, 1, 15, 0, 0, 0, tzinfo=dt_timezone.utc)


# --- user: nullable + SET_NULL (adaptación deliberada vs Odoo required) ----

def test_user_nullable_por_defecto():
    cron = IrCron.objects.create(
        ir_actions_server=_accion('Sin usuario', 'orders.Order', 'run'),
        nextcall=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
    )
    assert cron.user_id is None


def test_user_set_null_al_borrar_usuario():
    user = UserFactory()
    cron = IrCron.objects.create(
        ir_actions_server=_accion('Con usuario', 'orders.Order', 'run'),
        nextcall=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
        user=user,
    )
    user.delete()
    cron.refresh_from_db()
    assert cron.user_id is None


# --- interval_number > 0 (CheckConstraint, réplica de Odoo) ----------------

def test_interval_number_cero_viola_check_constraint():
    with pytest.raises(IntegrityError), transaction.atomic():
        IrCron.objects.create(
            ir_actions_server=_accion('Invalido', 'orders.Order', 'run'),
            nextcall=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
            interval_number=0,
        )


# --- __str__ -----------------------------------------------------------

def test_str_devuelve_name():
    cron = IrCron.objects.create(
        ir_actions_server=_accion('Mi tarea', 'orders.Order', 'run'),
        nextcall=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
    )
    assert str(cron) == 'Mi tarea'
