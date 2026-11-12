"""Los cinco cálculos de ``project.sale.line.employee.map`` siguen a sus
dependencias como en la fuente.

≙ ``odoo19c: addons/sale_timesheet/models/project_sale_line_employee_map.py``
(odoo-tools ``abe4040ec1``): ``_compute_price_unit`` y ``_compute_currency_id``
dependen de ``sale_line_id.price_unit``; ``_compute_cost`` de
``employee_id.hourly_cost`` y respeta el costo escrito a mano;
``_compute_is_cost_changed`` de ``cost``. Los cuatro son ``store=True``: la
columna sigue al registro relacionado aunque el mapa no se guarde.
designs/project-sale-line-employee-map-port.md, paso 1.
"""
from decimal import Decimal

import pytest
from django.apps import apps

from addons.project.models import Project
from addons.sale.models import SaleOrderLine
from tests.factories.order_factory import make_order
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db

EmployeeMap = apps.get_model('sale_timesheet', 'ProjectSaleLineEmployeeMap')
HrEmployee = apps.get_model('hr', 'HrEmployee')


@pytest.fixture
def project():
    return Project.objects.create(name='Proyecto con tarifas')


@pytest.fixture
def employee():
    return HrEmployee.objects.create(name='Consultora',
                                     hourly_cost=Decimal('40.00'))


@pytest.fixture
def sale_line(user):
    product = make_product(name='Hora de consultoría')
    return SaleOrderLine.objects.create(
        order=make_order(user=user), product=product, name=product.name,
        price_unit=Decimal('90.00'), product_uom_qty=1)


def _map(project, employee, **values):
    return EmployeeMap.objects.create(project=project, employee=employee,
                                      **values)


def _reload(entry):
    return EmployeeMap.objects.get(pk=entry.pk)


def test_the_price_and_currency_come_from_the_sale_line(project, employee,
                                                        sale_line):
    entry = _reload(_map(project, employee, sale_line=sale_line))
    assert entry.price_unit == pytest.approx(90.0)
    assert entry.currency_id == sale_line.currency_id


def test_without_a_sale_line_the_price_is_zero(project, employee):
    entry = _reload(_map(project, employee))
    assert entry.price_unit == 0
    assert entry.currency_id is None


def test_changing_the_line_price_recomputes_the_stored_price(
        project, employee, sale_line):
    entry = _map(project, employee, sale_line=sale_line)
    sale_line.price_unit = Decimal('120.00')
    sale_line.save()
    assert _reload(entry).price_unit == pytest.approx(120.0)


def test_the_cost_follows_the_employee_hourly_cost(project, employee):
    entry = _map(project, employee)
    assert _reload(entry).cost == Decimal('40.00')
    employee.hourly_cost = Decimal('55.00')
    employee.save()
    entry = _reload(entry)
    assert entry.cost == Decimal('55.00')
    assert entry.is_cost_changed is False


def test_a_cost_written_by_hand_stops_following_the_employee(project,
                                                             employee):
    entry = _map(project, employee)
    entry.cost = Decimal('70.00')
    entry.save()
    assert _reload(entry).is_cost_changed is True
    employee.hourly_cost = Decimal('60.00')
    employee.save()
    entry = _reload(entry)
    assert entry.cost == Decimal('70.00')
    assert entry.is_cost_changed is True
