"""Comandos sobre un ``One2many`` declarado en un registro de ``new()``.

≙ ``odoo19c: odoo/orm/fields_relational.py:589-641``
(``_RelationalMulti.convert_to_cache``), que ``_update_cache``
(``odoo19c: odoo/orm/models.py``, ``new``) llama para cada valor. Caso real:
la guarda ``if self.model_id`` de ``_get_warning_messages``
(``odoo19c: odoo/addons/base/models/ir_actions.py:765``) sólo es alcanzable en
un registro del formulario, con sus hijas dadas por comando.
"""

import pytest

from addons.base.models import IrActionsServer, IrModel
from orm.environments import Environment, sudo
from orm.fields_relational import One2many

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _child(name, model):
    return IrActionsServer.create({
        'name': name, 'state': 'multi', 'model_id': IrModel._get_id(model)})


def test_the_declared_one2many_converts_to_the_cache():
    assert callable(getattr(One2many, 'convert_to_cache', None))


def test_new_with_a_set_command_holds_the_children():
    child = _child('Hija', 'res.partner')
    record = Environment()['ir.actions.server'].new({
        'name': 'Formulario', 'state': 'multi',
        'child_ids': [(6, 0, [child.id])]})
    assert record.child_ids.ids == [child.id]


def test_the_model_guard_of_the_warning_is_reached_on_a_new_record():
    """Sin ``model_id`` en el formulario, una hija con modelo no avisa por
    modelo: la guarda ``if self.model_id`` (``:765``) corta la rama."""
    child = _child('Hija', 'res.country')
    record = Environment()['ir.actions.server'].new({
        'name': 'Formulario', 'state': 'multi',
        'child_ids': [(6, 0, [child.id])]})
    assert not record.warning


def test_with_a_model_the_same_children_do_warn():
    """CONTROL de la dirección contraria: con ``model_id`` la guarda deja
    pasar la rama y la hija de otro modelo avisa."""
    child = _child('Hija', 'res.country')
    record = Environment()['ir.actions.server'].new({
        'name': 'Formulario', 'state': 'multi',
        'model_id': IrModel._get_id('res.partner'),
        'child_ids': [(6, 0, [child.id])]})
    assert record.warning


def test_a_child_of_the_same_model_does_not_warn_on_a_new_record():
    """La hija es ``NewId(origin=...)``: su ``model_id`` se lee de la fila
    que la origina (``odoo19c: odoo/orm/fields.py:1715-1734``). Leída como
    vacía, una hija del mismo modelo avisaría por modelo distinto."""
    child = _child('Hija', 'res.partner')
    record = Environment()['ir.actions.server'].new({
        'name': 'Formulario', 'state': 'multi',
        'model_id': IrModel._get_id('res.partner'),
        'child_ids': [(6, 0, [child.id])]})
    assert record.child_ids.model_id == child.model_id
    assert not record.warning
