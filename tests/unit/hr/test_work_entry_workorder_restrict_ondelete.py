"""Entradas de trabajo y órdenes de trabajo con ``ondelete='restrict'``.

≙ ``odoo19c: addons/hr_work_entry/models/hr_work_entry.py:25-26``,
``addons/hr_work_entry/models/hr_user_work_entry_employee.py:13`` y
``addons/mrp/models/mrp_workorder.py:44``: Many2one obligatorios sin
``ondelete``, cuyo defecto es ``restrict`` (``odoo/orm/
fields_relational.py:274-282``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
hr-workorder-restrict-ondelete.md``.
"""
import datetime
from decimal import Decimal

import pytest
from django.db.models import ProtectedError

from addons.hr.models import HrEmployee, HrVersion
from addons.hr_work_entry.models import HrUserWorkEntryEmployee, HrWorkEntry
from addons.mrp.models import MrpProduction, MrpWorkcenter, MrpWorkorder
from addons.product.models import ProductProduct, ProductTemplate

pytestmark = pytest.mark.django_db


def _refuses_and_keeps(parent, child):
    with pytest.raises(ProtectedError):
        type(parent).objects.filter(pk=parent.pk).delete()
    assert type(child).objects.filter(pk=child.pk).exists()


def _employee_and_version(name):
    employee = HrEmployee.objects.create(name=name)
    version = HrVersion.objects.create(
        employee=employee, date_version=datetime.date(2026, 1, 1))
    return employee, version


def test_deleting_an_employee_with_work_entries_is_refused():
    """La versión es de otro empleado: al medido sólo lo protege la
    entrada (una versión propia también apunta a él)."""
    _owner, version = _employee_and_version('Dueño de la versión')
    employee = HrEmployee.objects.create(name='Con entradas')
    entry = HrWorkEntry.objects.create(
        employee=employee, version=version, date=datetime.date(2026, 1, 5))
    _refuses_and_keeps(employee, entry)


def test_deleting_a_version_with_work_entries_is_refused():
    employee, version = _employee_and_version('Con versión')
    entry = HrWorkEntry.objects.create(
        employee=employee, version=version, date=datetime.date(2026, 1, 6))
    _refuses_and_keeps(version, entry)


def test_deleting_an_employee_in_a_work_entry_filter_is_refused(user):
    employee = HrEmployee.objects.create(name='En filtro')
    row = HrUserWorkEntryEmployee.objects.create(user=user,
                                                 employee=employee)
    _refuses_and_keeps(employee, row)


def test_deleting_a_production_with_workorders_is_refused():
    template = ProductTemplate.objects.create(name='Mesa',
                                              list_price=Decimal('1.00'))
    product = ProductProduct.objects.create(product_tmpl=template)
    production = MrpProduction.objects.create(product=product,
                                              product_qty=Decimal('1'))
    workorder = MrpWorkorder.objects.create(
        production=production,
        workcenter=MrpWorkcenter.objects.create(name='Centro'))
    _refuses_and_keeps(production, workorder)
