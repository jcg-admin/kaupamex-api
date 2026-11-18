"""Borrar un empleado deja sus versiones con el empleado vacío.

``hr.version.employee_id`` no es obligatorio ni declara ``ondelete``
(``odoo19c: addons/hr/models/hr_version.py:54-59``): ``set null``. El
empleado no guarda columna hacia la versión y su ``unlink`` no las toca
(``odoo19c: addons/hr/models/hr_employee.py:1473-1476``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
set-null-hr-version-employee.md``.
"""
from datetime import date

import pytest

from addons.hr.models import HrEmployee, HrVersion
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def test_deleting_an_employee_keeps_its_versions():
    employee = HrEmployee.objects.create(name='Empleada con versión')
    version = HrVersion.objects.create(employee=employee,
                                       date_version=date(2026, 1, 1))
    version_ids = [version.pk]
    HrEmployee.objects.filter(pk=employee.pk).delete()
    remaining = HrVersion.objects.filter(pk__in=version_ids)
    assert sorted(remaining.values_list('pk', flat=True)) == version_ids
    assert set(remaining.values_list('employee_id', flat=True)) == {None}
