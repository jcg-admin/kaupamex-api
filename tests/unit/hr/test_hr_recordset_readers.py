"""Los lectores de ``hr`` y ``hr_fleet`` sobre inversos de ``BaseModel``.

``hr.employee``, ``hr.version``, ``hr.employee.category``,
``resource.resource`` y ``fleet.vehicle`` son ``BaseModel``: sus One2many y
Many2many son recordsets, como en la fuente, y estos sitios los leían con el
gestor de Django (``order_by``, ``all``, ``first``, ``values_list``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-reverse-queryset.md``.

≙ ``odoo19c: addons/hr/models/hr_employee.py`` (``_get_version_periods``,
``:1594-1624``), ``res_users.py`` (``category_ids``), ``resource.py`` y
``resource_calendar_leaves.py`` (``:14-33``), y
``odoo19c: addons/hr_fleet/models/employee.py`` (``:32-38``) y
``mail_activity_plan_template.py``.

*Métrica:* cada lector sobre registros creados por el ORM.
*Ciega a:* el troceo por zonas horarias de los periodos con varias versiones.
"""
from datetime import datetime, timezone

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from addons.hr.models.hr_employee import HrEmployee
from addons.hr.models.resource import _first_employee
from addons.hr_fleet.models.mail_activity_plan_template import (
    _determine_responsible)
from orm.environments import sudo

pytestmark = pytest.mark.django_db

FleetVehicle = apps.get_model('fleet', 'FleetVehicle')
FleetVehicleModel = apps.get_model('fleet', 'FleetVehicleModel')
FleetVehicleModelBrand = apps.get_model('fleet', 'FleetVehicleModelBrand')
HrEmployeeCategory = apps.get_model('hr', 'HrEmployeeCategory')
ResourceCalendarLeaves = apps.get_model('resource', 'ResourceCalendarLeaves')


@pytest.fixture
def employee():
    return HrEmployee.objects.create(name='HRR Empleado')


@pytest.fixture
def vehicle(employee):
    brand = FleetVehicleModelBrand.objects.create(name='HRR Marca')
    model = FleetVehicleModel.objects.create(name='HRR Modelo', brand=brand)
    return FleetVehicle.objects.create(
        model=model, license_plate='HRR-001', driver_employee=employee)


def test_the_version_periods_walk_the_versions(employee):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2026, 12, 31, tzinfo=timezone.utc)
    with sudo():
        periods = HrEmployee._get_version_periods(
            HrEmployee.objects.filter(pk=employee.pk), start, stop)
    assert isinstance(periods, dict)


def test_the_user_category_is_the_employee_tags(employee):
    tag = HrEmployeeCategory.objects.create(name='HRR Etiqueta')
    user = get_user_model().objects.create_user(
        login='hrr@kaupamex.mx', password='Hrr12345!')
    HrEmployee.objects.filter(pk=employee.pk).update(user_id=user)
    with sudo():
        HrEmployee.objects.get(pk=employee.pk).write(
            {'category': [(6, 0, [tag.pk])]})
        categories = get_user_model().objects.get(pk=user.pk).category
        assert [c.id for c in categories] == [tag.pk]


def test_the_first_employee_of_a_resource(employee):
    with sudo():
        resource = HrEmployee.objects.get(pk=employee.pk).resource
        assert _first_employee(resource).pk == employee.pk


def test_a_leave_of_an_employee_resource_computes_its_calendar(employee):
    with sudo():
        resource = HrEmployee.objects.get(pk=employee.pk).resource
        leave = ResourceCalendarLeaves(
            name='HRR Ausencia', resource=resource,
            date_from=datetime(2026, 3, 2, 9),
            date_to=datetime(2026, 3, 2, 17))
        leave._compute_calendar_id()


def test_the_license_plate_reads_the_vehicles(employee, vehicle):
    with sudo():
        assert HrEmployee.objects.get(
            pk=employee.pk)._compute_license_plate() == 'HRR-001'


def test_the_fleet_manager_reads_the_first_vehicle(employee, vehicle):
    with sudo():
        result = _determine_responsible(
            'fleet_manager', HrEmployee.objects.get(pk=employee.pk))
    assert result is not None
