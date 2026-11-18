"""``display_cost`` de ``project.sale.line.employee.map``: el costo en la
unidad de captura de la hoja de horas de la empresa.

≙ ``odoo19c: addons/sale_timesheet/models/project_sale_line_employee_map.py``:
el campo (``:37``), ``_get_working_hours_per_calendar`` (``:84-99``),
``_compute_display_cost`` (``:101-111``) e ``_inverse_display_cost``
(``:113-121``). Con la empresa capturando en días, el costo horario se
multiplica por las horas diarias del calendario del empleado; sin
calendario, el factor es 1. Diseño en
``designs/project-sale-line-employee-map-port.md`` (paso H2).

*Métrica:* ``display_cost`` leído por el ORM con la empresa activa, y
``cost`` leído de la columna tras escribir ``display_cost``.
*Ciega a:* ``groups=`` (se lee como superusuario) y a ``company_id``,
``partner_id`` y ``cost_currency_id``, que siguen como propiedades.
"""
from decimal import Decimal

import pytest
from django.apps import apps

from addons.base.models import ResCompany
from addons.project.models import Project
from addons.resource.models import ResourceCalendar
from orm.environments import company_scope, sudo
from orm.environments import env as current_env

pytestmark = pytest.mark.django_db

EmployeeMap = apps.get_model('sale_timesheet', 'ProjectSaleLineEmployeeMap')
HrEmployee = apps.get_model('hr', 'HrEmployee')


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _company(encode_xmlid):
    company = ResCompany.objects.create(
        code=f'acme-{encode_xmlid.split("_")[-1]}', name='ACME')
    company.write({'timesheet_encode_uom_id':
                   current_env().ref(encode_xmlid).id})
    return company


def _map(company, with_calendar=True):
    calendar = None
    if with_calendar:
        calendar = ResourceCalendar.objects.create(
            name='Estándar', company=company)
        calendar.create_default_attendances()
    employee = HrEmployee.objects.create(
        name='Consultora', hourly_cost=Decimal('40.00'))
    employee.resource_calendar = calendar
    employee.save()
    project = Project.objects.create(name='Proyecto', company=company)
    return EmployeeMap.objects.create(project=project, employee=employee)


def test_display_cost_is_the_hourly_cost_when_encoding_in_hours():
    company = _company('uom.product_uom_hour')
    entry = _map(company)
    with company_scope(company.id):
        assert entry.display_cost == Decimal('40.00')


def test_display_cost_is_the_daily_cost_when_encoding_in_days():
    company = _company('uom.product_uom_day')
    entry = _map(company)
    with company_scope(company.id):
        assert entry.display_cost == Decimal('320.00')


def test_writing_display_cost_in_days_stores_the_hourly_cost():
    company = _company('uom.product_uom_day')
    entry = _map(company)
    with company_scope(company.id):
        entry.write({'display_cost': Decimal('400.00')})
        entry.flush_model()
    assert EmployeeMap.objects.get(pk=entry.pk).cost == Decimal('50.00')


def test_an_employee_without_calendar_keeps_factor_one_in_days():
    company = _company('uom.product_uom_day')
    entry = _map(company, with_calendar=False)
    with company_scope(company.id):
        assert entry.display_cost == Decimal('40.00')
