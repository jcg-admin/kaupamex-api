"""``model_id`` de ``ir.actions.server`` y ``model_name`` como su ``related``.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:635-638`` (los campos) y
``:746-760, :803-804`` (``_compute_warning`` con sus dependencias).
Diseño: ``designs/ir-actions-server-model-id.md``.
"""

import pytest

from addons.base.models import IrActionsServer, IrModel
from orm.environments import sudo

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _model(name):
    return IrModel._get(name)


def test_model_id_is_a_required_many2one_to_ir_model():
    field = IrActionsServer._meta.get_field('model_id')
    assert (field.column, field.related_model, field.null) == (
        'model_id', IrModel, False)
    assert IrActionsServer._fields['model_id'].ondelete == 'cascade'


def test_model_name_is_the_related_of_model_id():
    """``model_name`` no tiene columna: se lee de ``model_id.model``."""
    assert not IrActionsServer._meta.get_field('model_name').concrete
    action = IrActionsServer.create({
        'name': 'Socios', 'model_id': _model('res.partner').pk})
    assert action.model_name == 'res.partner'


def test_a_child_takes_the_model_of_its_parent():
    """``create`` (``:711-728``): el hijo toma ``model_id`` del padre."""
    parent = IrActionsServer.create({
        'name': 'Madre', 'state': 'multi',
        'model_id': _model('res.partner').pk})
    child = IrActionsServer.create({
        'name': 'Hija', 'parent_id': parent.id})
    assert child.model_id == parent.model_id


def test_the_warning_follows_a_child_model_change():
    """``@api.depends(lambda self: self._warning_depends())``: cambiar el
    modelo de una hija recalcula el aviso del padre sin volver a leerlo a
    mano."""
    parent = IrActionsServer.create({
        'name': 'Madre', 'state': 'multi',
        'model_id': _model('res.partner').pk})
    child = IrActionsServer.create({
        'name': 'Hija', 'model_id': _model('res.partner').pk})
    parent.write({'child_ids': [(4, child.id)]})
    assert not parent.warning
    child.write({'model_id': _model('res.country').pk})
    assert parent.warning
