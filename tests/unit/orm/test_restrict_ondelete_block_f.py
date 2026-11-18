"""Bloque F: una empresa con filas que la exigen no se borra.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
restrict-ondelete-block-f.md``. Un ``Many2one`` obligatorio sin ``ondelete``
es ``restrict`` (``odoo19c: odoo/orm/fields_relational.py:274-282``) y
``res.company.unlink`` no borra antes a ningún hijo
(``odoo19c: odoo/addons/base/models/res_company.py:347-353``). El atributo
de las 23 filas está en ``test_delete_policy_contract.py``.

Un fixture por hijo, para que ninguno proteja a la empresa en lugar de otro.

*Métrica:* que el borrado se rehúsa y la fila hija sigue en la base.
*Ciega a:* el error con que la fuente rehúsa, que es de integridad de la
base y aquí es ``ProtectedError``.
"""
import pytest
from django.apps import apps
from django.db import models

from addons.base.models import ResCompany
from orm.environments import sudo

pytestmark = pytest.mark.django_db

AccountJournal = apps.get_model('account', 'AccountJournal')
AccountTax = apps.get_model('account', 'AccountTax')
AccountTaxGroup = apps.get_model('account', 'AccountTaxGroup')
AccountGroup = apps.get_model('account', 'AccountGroup')


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def company():
    return ResCompany.objects.create(code='block-f', name='Bloque F')


def _journal(company):
    return AccountJournal.objects.create(
        name='Diario F', code='BLKF', type='general', company=company)


def _tax_group(company):
    return AccountTaxGroup.objects.create(name='Grupo F', company=company)


def _tax(company):
    return AccountTax.objects.create(name='Impuesto F', company=company)


def _account_group(company):
    return AccountGroup.objects.create(name='Grupo de cuentas F',
                                       company=company)


@pytest.mark.parametrize('child', [_journal, _tax_group, _tax,
                                   _account_group])
def test_a_company_with_a_dependent_row_is_protected(company, child):
    row = child(company)
    with pytest.raises(models.ProtectedError):
        ResCompany.objects.filter(pk=company.pk).delete()
    assert type(row).objects.filter(pk=row.pk).exists()
    assert ResCompany.objects.filter(pk=company.pk).exists()


def test_a_company_without_dependent_rows_is_deleted(company):
    ResCompany.objects.filter(pk=company.pk).delete()
    assert not ResCompany.objects.filter(pk=company.pk).exists()
