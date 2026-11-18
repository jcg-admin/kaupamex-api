"""``partner_id`` de ``account.payment`` apunta a ``res.partner``.

≙ ``odoo19c: addons/account/models/account_payment.py:116``:
``Many2one('res.partner', string="Customer/Vendor", ondelete='restrict',
...)``. Aquí apuntaba al usuario con ``SET_NULL``.

Métrica: el destino y la política de la clave, la fila del pago tras
intentar borrar su partner, y la columna ``partner_id`` tras la operación
de datos de la migración 0049.
Ciega a: ``domain`` y ``check_company``, que no se ejercitan.
"""
import importlib
from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection, models
from django.db.models import RestrictedError

from addons.account.models import AccountJournal, AccountPayment
from addons.base.models import ResCompany, ResPartner
from orm.environments import env, sudo
from orm.utils import model_field_registry

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def journal():
    company = ResCompany.objects.create(name='Pagos socio', code='pay-part')
    return AccountJournal.objects.create(
        name='Banco', code='PPT', type='bank', company=company)


def _payment(journal, **values):
    payment = env()['account.payment'].create({
        'amount': Decimal('10.00'), 'journal': journal.pk,
        'company': journal.company_id, **values})
    env().flush_all()
    return payment


def test_the_field_targets_res_partner_with_restrict():
    field = model_field_registry(AccountPayment)['partner']
    assert field.related_model is ResPartner
    assert field.ondelete == 'restrict'
    assert field.remote_field.on_delete is models.RESTRICT


def test_a_partner_with_payments_is_not_deleted(journal):
    partner = ResPartner.objects.create(name='Con pagos')
    payment = _payment(journal, partner=partner.pk)
    with pytest.raises(RestrictedError):
        ResPartner.objects.filter(pk=partner.pk).delete()
    assert AccountPayment.objects.filter(
        pk=payment.id, partner_id=partner.pk).exists()


def test_migration_0049_replaces_the_user_by_its_partner(journal):
    """Una fila anterior guarda el id de un usuario: la operación deja el id
    de su partner. Se lee con SQL: la lectura del ORM devolvería la caché."""
    user = get_user_model().objects.create_user(
        login='pago-usuario', password=None, name='Usuario del pago')
    assert user.pk != user.partner_id
    payment = _payment(journal)
    with connection.cursor() as cursor:
        # El estado anterior a la migración: la columna sin restricción
        # contra ``res_partner`` y con el id de un usuario dentro.
        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE contype = 'f' "
            "AND conrelid = 'account_payment'::regclass "
            "AND confrelid = 'res_partner'::regclass")
        [(constraint,)] = cursor.fetchall()
        cursor.execute('ALTER TABLE account_payment DROP CONSTRAINT '
                       + connection.ops.quote_name(constraint))
        cursor.execute(
            'UPDATE account_payment SET partner_id = %s WHERE id = %s',
            [user.pk, payment.id])
    module = importlib.import_module(
        'addons.account.migrations.0049_payment_partner_res_partner')
    with connection.schema_editor() as editor:
        module.users_to_partners(apps, editor)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT partner_id FROM account_payment WHERE id = %s',
            [payment.id])
        assert cursor.fetchone() == (user.partner_id,)
