"""``hr.department`` sobre ``BaseModel``, con ``_parent_store``.

≙ ``odoo19c: addons/hr/models/hr_department.py:17,115-118``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
hr-department-basemodel.md``.
"""
import pytest

from exceptions import UserError
from orm.environments import sudo
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    """Los datos de prueba de la referencia se escriben como superusuario."""
    with sudo():
        yield


def _department(name, parent=None):
    vals = {'name': name}
    if parent is not None:
        vals['parent_id'] = parent.id
    [department] = MODELS_BY_NAME['hr.department'].create([vals])
    return department


def _path(department):
    return MODELS_BY_NAME['hr.department'].objects.filter(
        pk=department.id).values_list('parent_path', flat=True).get()


def test_the_department_is_a_base_model():
    assert issubclass(MODELS_BY_NAME['hr.department'], BaseModel)


def test_creating_a_child_materializes_its_path():
    root = _department('Raíz')
    child = _department('Hijo', root)
    assert _path(child) == f'{root.id}/{child.id}/'


def test_moving_a_department_rewrites_its_subtree():
    first, second = _department('Uno'), _department('Dos')
    middle = _department('Medio', first)
    leaf = _department('Hoja', middle)
    middle.write({'parent_id': second.id})
    assert _path(leaf) == f'{second.id}/{middle.id}/{leaf.id}/'


def test_a_cycle_is_refused():
    """``_parent_store_update`` lo rechaza antes que la restricción, como
    en la fuente (``odoo19c: odoo/orm/models.py:5030``)."""
    root = _department('Raíz ciclo')
    child = _department('Hijo ciclo', root)
    with pytest.raises(UserError, match='Recursion Detected'):
        root.write({'parent_id': child.id})
