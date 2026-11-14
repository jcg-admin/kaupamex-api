"""``hr.employee.location`` sobre ``BaseModel``.

≙ ``odoo19c: addons/hr_homeworking/models/hr_homeworking.py`` y su seguridad
(``security/ir.model.access.csv`` y ``security/security.xml``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
hr-employee-location-basemodel.md``.
"""
import datetime

import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from addons.hr.models import HrEmployee, HrWorkLocation
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME
from tools.misc import format_date

pytestmark = pytest.mark.django_db

MONDAY = datetime.date(2026, 11, 16)


def _user(login, *xmlids):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for xmlid in xmlids:
        module, name = xmlid.split('.')
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData.objects.get(module=module, name=name).res_id))
    return user


def _location(employee, place, day=MONDAY):
    [row] = MODELS_BY_NAME['hr.employee.location'].create([{
        'employee_id': employee.pk,
        'work_location_id': place.pk,
        'date': day,
    }])
    return row


@pytest.fixture
def place():
    return HrWorkLocation.objects.create(name='Casa', location_type='home')


def test_the_employee_location_is_a_base_model():
    assert issubclass(MODELS_BY_NAME['hr.employee.location'], BaseModel)


def test_related_fields_follow_their_path(place):
    employee = HrEmployee.objects.create(name='Ana')
    with sudo():
        row = _location(employee, place)
        assert row.work_location_name == 'Casa'
        assert row.work_location_type == 'home'
        assert row.employee_name == 'Ana'


def test_day_week_string_is_the_ldml_day_name(place):
    """≙ ``tools.format_date(record.env, record.date, date_format='EEEE')``."""
    employee = HrEmployee.objects.create(name='Ana')
    with sudo():
        row = _location(employee, place)
        assert row.day_week_string == format_date(
            row.env, MONDAY, date_format='EEEE')


def test_the_employee_defaults_to_the_acting_user(place):
    """≙ ``default=lambda self: self.env.user.employee_id``."""
    user = _user('homeworking-default', 'base.group_user')
    with sudo():
        employee = HrEmployee.objects.create(name='Beto', user_id=user)
    with user_scope(user.pk):
        [row] = Environment(uid=user.pk)['hr.employee.location'].create([{
            'work_location_id': place.pk, 'date': MONDAY,
        }])
        assert row.employee_id.id == employee.pk


def test_an_internal_user_sees_only_their_own_rows(place):
    """≙ la regla ``homeworking_own_rule``."""
    user = _user('homeworking-own', 'base.group_user')
    with sudo():
        mine = HrEmployee.objects.create(name='Carla', user_id=user)
        other = HrEmployee.objects.create(name='Dario')
        own = _location(mine, place)
        _location(other, place)
    with user_scope(user.pk):
        found = Environment(uid=user.pk)['hr.employee.location'].search([])
        assert found.ids == [own.id]


def test_an_hr_officer_sees_every_row(place):
    """≙ la regla ``homeworking_admin_rule``."""
    user = _user('homeworking-admin', 'base.group_user', 'hr.group_hr_user')
    with sudo():
        rows = [_location(HrEmployee.objects.create(name=name), place)
                for name in ('Eva', 'Fito')]
    with user_scope(user.pk):
        found = Environment(uid=user.pk)['hr.employee.location'].search([])
        assert set(found.ids) >= {row.id for row in rows}
