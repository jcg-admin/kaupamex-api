"""Los lectores de ``timesheets`` sobre un inverso de ``BaseModel``.

Desde que ``account.analytic.line`` es ``BaseModel`` (etapa 1a de
analítica), el inverso ``timesheets`` de un empleado, un proyecto o una tarea
—todos ``BaseModel``— es un recordset, como en la fuente. Estos tres
cómputos lo leían con el gestor de Django (``filter``, ``aggregate``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-reverse-queryset.md``.

≙ ``_compute_has_timesheet`` (``odoo19c: hr_timesheet/models/hr_employee.py:
13-29``), ``_compute_remaining_hours`` (``project_project.py:68-79``) y
``_compute_effective_hours`` (``project_task.py:83-92``).

*Métrica:* los tres valores sobre partes creados por el ORM.
*Ciega a:* la conversión de unidad de medida, que el puerto declara fuera.
"""
import pytest
from django.apps import apps

from addons.analytic.models import (
    AccountAnalyticAccount, AccountAnalyticLine, AccountAnalyticPlan)
from addons.base.models.res_company import ResCompany
from orm.environments import sudo

pytestmark = pytest.mark.django_db

HrEmployee = apps.get_model('hr', 'HrEmployee')
Project = apps.get_model('project', 'Project')
ProjectTask = apps.get_model('project', 'ProjectTask')


@pytest.fixture
def world():
    company = ResCompany.objects.create(code='trr-a', name='TRR')
    plan = AccountAnalyticPlan.objects.create(name='TRR Plan')
    account = AccountAnalyticAccount.objects.create(
        name='TRR Cuenta', plan_id=plan, company_id=company)
    employee = HrEmployee.objects.create(name='TRR Empleado')
    project = Project.objects.create(name='TRR Proyecto')
    task = ProjectTask.objects.create(name='TRR Tarea', project=project)
    return company, account, employee, project, task


def _timesheet(company, account, employee, hours, project=None, task=None):
    return AccountAnalyticLine.objects.create(
        name='TRR Parte', account=account, amount=0, company=company,
        employee=employee, project=project, task=task, unit_amount=hours)


def test_an_employee_has_timesheets_only_with_a_project(world):
    company, account, employee, project, _task = world
    _timesheet(company, account, employee, 1)
    with sudo():
        assert HrEmployee.objects.get(pk=employee.pk).has_timesheet is False
    _timesheet(company, account, employee, 1, project=project)
    with sudo():
        assert HrEmployee.objects.get(pk=employee.pk).has_timesheet is True


def test_the_project_effective_hours_sum_its_timesheets(world):
    company, account, employee, project, _task = world
    _timesheet(company, account, employee, 1.5, project=project)
    _timesheet(company, account, employee, 2.25, project=project)
    with sudo():
        assert Project.objects.get(pk=project.pk).effective_hours == 3.75


def test_the_task_effective_hours_sum_its_timesheets(world):
    company, account, employee, project, task = world
    _timesheet(company, account, employee, 0.5, project=project, task=task)
    _timesheet(company, account, employee, 4, project=project, task=task)
    with sudo():
        assert ProjectTask.objects.get(pk=task.pk).effective_hours == 4.5
