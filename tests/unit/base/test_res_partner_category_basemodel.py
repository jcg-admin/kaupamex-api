"""``res.partner.category`` sobre ``BaseModel``.

≙ ``odoo19c: odoo/addons/base/models/res_partner.py:139-181``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
res-partner-category-basemodel.md``.
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


def _tag(name, parent=None):
    vals = {'name': name}
    if parent is not None:
        vals['parent_id'] = parent.id
    [tag] = MODELS_BY_NAME['res.partner.category'].create([vals])
    return tag


def test_the_category_is_a_base_model():
    assert issubclass(MODELS_BY_NAME['res.partner.category'], BaseModel)


def test_create_deals_a_color_between_one_and_eleven():
    """≙ ``color = fields.Integer(default=_get_default_color)`` (:145-149)."""
    assert 1 <= _tag('Clientes').color <= 11


def test_reparenting_rewrites_the_whole_subtree():
    first = _tag('Primera')
    second = _tag('Segunda')
    child = _tag('Hija', first)
    grandchild = _tag('Nieta', child)
    child.write({'parent_id': second.id})
    assert child.parent_path == f'{second.id}/{child.id}/'
    assert grandchild.parent_path == f'{second.id}/{child.id}/{grandchild.id}/'


def test_a_cycle_by_write_is_rejected():
    """Con ``_parent_store``, el ciclo lo rechaza ``_parent_store_update``
    antes que la restricción, como en la fuente (``odoo/orm/models.py``,
    ``raise UserError(_("Recursion Detected."))``)."""
    root = _tag('A')
    child = _tag('B', root)
    with pytest.raises(UserError):
        root.write({'parent_id': child.id})


def test_partner_ids_lives_in_the_source_relation():
    """≙ ``partner_ids = fields.Many2many('res.partner',
    column1='category_id', column2='partner_id')`` (:154)."""
    model = MODELS_BY_NAME['res.partner.category']
    field = model._meta.get_field('partner_ids')
    through = field.remote_field.through._meta
    assert through.db_table == 'res_partner_res_partner_category_rel'
    assert {f.column for f in through.local_fields} >= {
        'category_id', 'partner_id'}
