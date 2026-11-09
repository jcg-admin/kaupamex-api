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
