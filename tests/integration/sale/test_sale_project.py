"""Tests — addons ``project`` + ``sale_project`` (línea de servicio → tarea)."""
from decimal import Decimal

import pytest

from addons.project.models import Project, ProjectTask, ProjectTaskType
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_project.models import SaleOrderLineProject
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


def test_project_task_type_ordering(db):
    b = ProjectTaskType.objects.create(name='Hecho', sequence=2)
    a = ProjectTaskType.objects.create(name='Nuevo', sequence=1)
    assert list(ProjectTaskType.objects.all()) == [a, b]


def test_project_task_defaults_and_closed(db):
    project = Project.objects.create(name='Instalación')
    task = ProjectTask.objects.create(project=project, name='Montaje')
    assert task.state == ProjectTask.STATE_IN_PROGRESS
    assert task.priority == '0'
    assert task.is_closed() is False
    task.state = ProjectTask.STATE_DONE
    assert task.is_closed() is True
    assert task in project.tasks.all()


def test_generate_task_from_service_line(db):
    product = make_product(name='Servicio de armado', price=Decimal('500.00'))
    order = SaleOrder.objects.create()
    line = SaleOrderLine.objects.create(
        order=order, product=product, price_unit=Decimal('500.00'),
        name='Armado a domicilio',
    )
    project = Project.objects.create(name='Proyecto cliente')
    link = SaleOrderLineProject.generate_task(line, project)
    assert line.project_link.task == link.task
    assert link.task.name == 'Armado a domicilio'
    assert link.project == project
    assert link.task in project.tasks.all()


def test_generate_task_idempotent(db):
    product = make_product(name='Servicio', price=Decimal('100.00'))
    order = SaleOrder.objects.create()
    line = SaleOrderLine.objects.create(
        order=order, product=product, price_unit=Decimal('100.00'), name='Tarea',
    )
    p1 = Project.objects.create(name='P1')
    p2 = Project.objects.create(name='P2')
    SaleOrderLineProject.generate_task(line, p1)
    SaleOrderLineProject.generate_task(line, p2)
    # Un único vínculo por línea (update_or_create).
    assert SaleOrderLineProject.objects.filter(line=line).count() == 1
    line.refresh_from_db()
    assert line.project_link.project == p2
    # Se crearon dos tareas (una por llamada); el vínculo apunta a la última.
    assert ProjectTask.objects.count() == 2
