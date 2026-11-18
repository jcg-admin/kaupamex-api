"""``date``, ``name`` y la secuencia de ``account.payment``.

≙ ``odoo19c: addons/account/models/account_payment.py:15`` (``name``),
``odoo19c: addons/account/models/account_payment.py:16`` (``date``),
``odoo19c: addons/account/models/account_payment.py:414``
(``_compute_name``) y ``odoo19c: addons/account/data/ir_sequence.xml:4``
(``seq_account_payment``). Son los dos campos que cita
``_order = "date desc, name desc"`` (``:11``).

Métrica: columnas ``name`` y ``date`` leídas de la base tras el volcado, y
filas de ``ir.sequence`` e ``ir.model.data``.
Ciega a: la rama ``move_id.name`` del cómputo, que no está portada.
"""
import datetime
import importlib
import re
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import DEFAULT_DB_ALIAS, connection

from addons.account.data import seed_payment_sequence
from addons.account.models import AccountJournal, AccountPayment
from addons.base.models import IrModelData, IrSequence, ResCompany
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def journal():
    company = ResCompany.objects.create(name='Pagos fecha', code='pay-date')
    return AccountJournal.objects.create(
        name='Banco', code='PDT', type='bank', company=company)


def _payment(journal, **values):
    return env()['account.payment'].create({
        'amount': Decimal('10.00'), 'journal': journal.pk,
        'company': journal.company_id, **values})


def _stored(payment):
    env().flush_all()
    return AccountPayment.objects.filter(pk=payment.id).values_list(
        'name', 'date').get()


def test_search_follows_the_declared_order(journal):
    old = _payment(journal, date=datetime.date(2026, 1, 5))
    new = _payment(journal, date=datetime.date(2026, 2, 5))
    found = env()['account.payment'].search(
        [('id', 'in', [old.id, new.id])])
    assert found.ids == [new.id, old.id]


def test_a_new_payment_is_dated_today(journal):
    payment = _payment(journal)
    assert _stored(payment)[1] == datetime.date.today()


def test_a_draft_payment_has_no_number(journal):
    assert not _stored(_payment(journal))[0]


def test_an_in_process_payment_takes_the_next_number(journal):
    payment = _payment(journal)
    payment.write({'state': 'in_process'})
    name = _stored(payment)[0]
    assert re.fullmatch(r'PAY\d{5}', name)


def test_the_number_is_taken_once(journal):
    payment = _payment(journal)
    payment.write({'state': 'in_process'})
    first = _stored(payment)[0]
    assert first
    payment.write({'state': 'paid'})
    assert _stored(payment)[0] == first


def test_seeding_twice_keeps_one_sequence():
    seed_payment_sequence(apps, DEFAULT_DB_ALIAS)
    seed_payment_sequence(apps, DEFAULT_DB_ALIAS)
    rows = IrSequence.objects.filter(code='account.payment')
    assert rows.count() == 1
    link = IrModelData.objects.get(module='account',
                                   name='seq_account_payment')
    assert link.res_id == rows.get().pk
    assert rows.get().prefix == 'PAY'
    assert rows.get().padding == 5
    assert rows.get().company_id is None


def test_migration_0048_dates_the_existing_rows(journal):
    """Una fila anterior a la columna recibe el día de su ``create_date``.
    Se lee con SQL: la lectura del ORM devolvería la caché."""
    payment = _payment(journal, date=datetime.date(2026, 1, 5))
    env().flush_all()
    with connection.cursor() as cursor:
        # Las restricciones diferidas de la transacción de la prueba
        # impiden un ``ALTER TABLE`` hasta comprobarse.
        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        cursor.execute('ALTER TABLE account_payment '
                       'ALTER COLUMN date DROP NOT NULL')
        cursor.execute(
            "UPDATE account_payment SET date = NULL, "
            "create_date = '2025-12-24 10:00:00+00' WHERE id = %s",
            [payment.id])
    module = importlib.import_module(
        'addons.account.migrations.0048_payment_date_name')
    with connection.schema_editor() as editor:
        module.fill_payment_date(apps, editor)
    with connection.cursor() as cursor:
        cursor.execute('SELECT date FROM account_payment WHERE id = %s',
                       [payment.id])
        assert cursor.fetchone() == (datetime.date(2025, 12, 24),)
        cursor.execute('ALTER TABLE account_payment '
                       'ALTER COLUMN date SET NOT NULL')
