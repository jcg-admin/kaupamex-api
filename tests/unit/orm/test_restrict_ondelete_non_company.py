"""Filas ``restrict`` sin empresa: el padre con hijos no se borra.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
restrict-ondelete-non-company.md`` (tramo A). Regla por defecto
``odoo19c: odoo/orm/fields_relational.py:274-282``: ``required`` sin
``ondelete`` es ``restrict``. Cada padre se midió: ninguno borra antes a
estos hijos. ``account.account`` además rehúsa con su mensaje
(``odoo19c: addons/account/models/account_account.py:1142-1145``).

Un fixture por hijo, para que ninguno proteja al padre en lugar del otro.
"""
from decimal import Decimal

import pytest
from django.apps import apps
from django.db import models

from addons.base.models import ResCompany
from exceptions import UserError
from orm.environments import sudo

pytestmark = pytest.mark.django_db

StockLocation = apps.get_model('stock', 'StockLocation')
StockRoute = apps.get_model('stock', 'StockRoute')
StockRule = apps.get_model('stock', 'StockRule')
Project = apps.get_model('project', 'Project')
HrEmployee = apps.get_model('hr', 'HrEmployee')
EmployeeMap = apps.get_model('sale_timesheet', 'ProjectSaleLineEmployeeMap')
AccountAccount = apps.get_model('account', 'AccountAccount')
FiscalPosition = apps.get_model('account', 'AccountFiscalPosition')
FiscalPositionAccount = apps.get_model('account',
                                       'AccountFiscalPositionAccount')


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _location(name):
    return StockLocation.objects.create(name=name, usage='internal')


def test_a_location_used_as_rule_destination_is_protected():
    location = _location('WH/Destino')
    rule = StockRule.objects.create(
        name='Regla', action=StockRule.ACTION_PULL,
        route=StockRoute.objects.create(name='Ruta'),
        location_dest=location)
    with pytest.raises(models.ProtectedError):
        StockLocation.objects.filter(pk=location.pk).delete()
    assert StockRule.objects.filter(pk=rule.pk).exists()


def test_a_location_without_rules_is_deleted():
    location = _location('WH/Libre')
    StockLocation.objects.filter(pk=location.pk).delete()
    assert not StockLocation.objects.filter(pk=location.pk).exists()


def _project():
    return Project.objects.create(name='Proyecto con mapa')


def _employee():
    return HrEmployee.objects.create(name='Consultora',
                                     hourly_cost=Decimal('40.00'))


def test_a_project_with_employee_rates_is_protected():
    project = _project()
    rate = EmployeeMap.objects.create(project=project, employee=_employee())
    with pytest.raises(models.ProtectedError):
        Project.objects.filter(pk=project.pk).delete()
    assert EmployeeMap.objects.filter(pk=rate.pk).exists()


def test_an_employee_with_project_rates_is_protected():
    employee = _employee()
    rate = EmployeeMap.objects.create(project=_project(), employee=employee)
    with pytest.raises(models.ProtectedError):
        HrEmployee.objects.filter(pk=employee.pk).delete()
    assert EmployeeMap.objects.filter(pk=rate.pk).exists()


@pytest.fixture
def company():
    return ResCompany.objects.create(name='Mapeo fiscal 0515')


def _account(company, code):
    return AccountAccount.objects.create(code=code, name=f'Cuenta {code}',
                                         account_type='income',
                                         company=company)


@pytest.mark.parametrize('side', ['account_src', 'account_dest'])
def test_a_mapped_account_is_refused_with_the_source_message(company, side):
    mapped, other = _account(company, '401'), _account(company, '402')
    position = FiscalPosition.objects.create(name='Extranjero',
                                             company=company)
    sides = {'account_src': other, 'account_dest': other, side: mapped}
    mapping = FiscalPositionAccount.objects.create(position=position, **sides)
    with pytest.raises(UserError, match='account mapping of a fiscal'):
        mapped.unlink()
    assert FiscalPositionAccount.objects.filter(pk=mapping.pk).exists()


def test_an_unmapped_account_is_deleted(company):
    account = _account(company, '409')
    account.unlink()
    assert not AccountAccount.objects.filter(pk=account.pk).exists()
