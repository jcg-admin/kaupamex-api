"""Las fechas de ``TimeStampedModel`` son la hora de la transacción.

``create`` y ``write`` de ``odoo19c`` fechan con ``cr.now()``
(``odoo/orm/models.py:4396,4803-4805``), que es ``NOW()`` de PostgreSQL:
la hora de inicio de la transacción, memorizada (``odoo/sql_db.py:271-278``).
Todo lo escrito en una misma transacción lleva la misma fecha.

*Métrica:* ``created_at``/``updated_at`` frente a ``SELECT now()``.
*Ciega a:* el modo autocommit fuera de ``atomic`` (cada sentencia es su
propia transacción y la igualdad no aplica).
"""
import time

import pytest
from django.db import connection, transaction

from addons.base.models import timestamped_mixin
from orm import fields_temporal
from orm.environments import env as current_env
from orm.environments import sudo

pytestmark = pytest.mark.django_db


def _transaction_now():
    with connection.cursor() as cursor:
        cursor.execute('SELECT now()')
        return cursor.fetchone()[0]


def test_a_write_in_the_create_transaction_keeps_the_date():
    with sudo(), transaction.atomic():
        e = current_env()
        record = e['test_orm.related'].create({'name': 'a'})
        e.flush_all()
        time.sleep(0.01)
        record.write({'name': 'b'})
        e.flush_all()
        assert record.updated_at == record.created_at


def test_two_creates_in_one_transaction_share_the_date():
    with sudo(), transaction.atomic():
        e = current_env()
        first = e['test_orm.related'].create({'name': 'a'})
        time.sleep(0.01)
        second = e['test_orm.related'].create({'name': 'b'})
        assert first.created_at == second.created_at


def test_the_date_is_the_transaction_timestamp():
    with sudo(), transaction.atomic():
        e = current_env()
        record = e['test_orm.related'].create({'name': 'a'})
        assert record.created_at == _transaction_now()


def test_a_savepoint_keeps_the_transaction_date():
    """``atomic`` anidado es un savepoint: la fuente no reinicia
    ``cr._now`` en él (``sql_db.py:560-576``, sólo ``commit``/``rollback``)."""
    with sudo(), transaction.atomic():
        e = current_env()
        outer = e['test_orm.related'].create({'name': 'a'})
        time.sleep(0.01)
        with transaction.atomic():
            inner = e['test_orm.related'].create({'name': 'b'})
        assert inner.created_at == outer.created_at


def test_one_insert_takes_both_dates_from_one_clock_reading(monkeypatch):
    """Fuera de ``atomic`` cada ``SELECT now()`` es su propia transacción
    (autocommit) y dos lecturas pueden diferir. La fuente fija
    ``create_date`` y ``write_date`` con el mismo ``cr.now()``
    (``models.py:4803-4805``). Se simula el autocommit con un reloj que
    avanza en cada lectura."""
    readings = iter(range(1, 100))
    base = _transaction_now()

    def advancing(using):
        return base.replace(microsecond=next(readings))

    monkeypatch.setattr(fields_temporal, 'transaction_now', advancing)
    with sudo():
        record = current_env()['test_orm.related'].create({'name': 'a'})
        assert record.created_at == record.updated_at


def test_the_clock_is_read_on_the_row_database(monkeypatch):
    """La consulta va a la base donde se escribe la fila. Durante el INSERT
    ``_state.db`` aún es ``None`` (Django lo fija después); el destino es el
    que ``save`` resuelve con ``router.db_for_write``."""
    seen = []
    real = timestamped_mixin.transaction_now

    def spy(using):
        seen.append(using)
        return real(using)

    monkeypatch.setattr(fields_temporal, 'transaction_now', spy)
    with sudo():
        current_env()['test_orm.related'].create({'name': 'a'})
    assert seen and set(seen) == {'default'}


def test_a_later_save_reads_the_clock_again(monkeypatch):
    """La lectura compartida dura un guardado: un ``save`` posterior —en otra
    transacción, simulada con el reloj que avanza— lee ``now()`` otra vez,
    como ``cr.now()`` tras el ``commit`` (``sql_db.py:560-565``)."""
    readings = iter(range(1, 100))
    base = _transaction_now()

    def advancing(using):
        return base.replace(microsecond=next(readings))

    monkeypatch.setattr(fields_temporal, 'transaction_now', advancing)
    Model = current_env()['test_orm.related']
    with sudo():
        row = Model(name='a')
        row.save()
        created = row.updated_at
        row.name = 'b'
        row.save()
        assert row.updated_at > created
