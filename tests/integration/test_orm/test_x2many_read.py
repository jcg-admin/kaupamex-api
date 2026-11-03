"""Leer un x2many devuelve un recordset del comodelo.

≙ ``_RelationalMulti.convert_to_record`` (``odoo19c: odoo/orm/
fields_relational.py``): el valor de un One2many o un Many2many sobre un
registro es un recordset del comodelo, con ``ids``, ``mapped`` y la
aritmética de recordsets. Aquí el descriptor de Django devolvía su gestor.
Sólo para dueño y comodelo ``BaseModel`` (los modelos de ``test_orm``).
"""

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def family(env):
    Parent, Child = env['test_orm.any.parent'], env['test_orm.any.child']
    Tag = env['test_orm.any.tag']
    parent = Parent.create({'name': 'Jean'})
    a = Child.create({'parent_id': parent.id, 'quantity': 1})
    b = Child.create({'parent_id': parent.id, 'quantity': 2})
    tag = Tag.create({'name': 't'})
    a.write({'tag_ids': [tag.id]})
    return parent, a, b, tag


def test_a_one2many_reads_as_a_recordset(env, family):
    parent, a, b, _ = family
    children = env['test_orm.any.parent'].browse(parent.ids).child_ids
    assert sorted(children.ids) == sorted([a.id, b.id])
    assert sorted(children.mapped('quantity')) == [1, 2]
    assert children == env['test_orm.any.child'].browse(children.ids)


def test_a_many2many_reads_as_a_recordset(env, family):
    _, a, _, tag = family
    tags = env['test_orm.any.child'].browse(a.ids).tag_ids
    assert tags.ids == [tag.id]
    assert tags.mapped('name') == ['t']
    assert env['test_orm.any.tag'].browse(tag.ids).child_ids.ids == [a.id]


def test_an_empty_relation_is_an_empty_recordset(env, family):
    _, _, b, _ = family
    tags = env['test_orm.any.child'].browse(b.ids).tag_ids
    assert not tags
    assert tags.ids == []


def test_assigning_a_recordset_to_a_one2many_sets_it(env):
    """``record.line_ids = lines`` escribe la relación — ≙ el ``SET`` de
    ``One2many.write_real`` que la fuente aplica a una asignación
    (``odoo19c: odoo/orm/fields_relational.py:1027``): las líneas quedan
    exactamente en ese conjunto y las que sobran se borran (``cascade``)."""
    Order, Line = env['test_orm.order'], env['test_orm.order.line']
    order = Order.create({})
    keep = Line.create({'order_id': order.id, 'product': 'keep'})
    drop = Line.create({'order_id': order.id, 'product': 'drop'})
    other = Order.create({})
    moved = Line.create({'order_id': other.id, 'product': 'moved'})

    record = Order.browse(order.ids)
    record.line_ids = keep | moved
    assert sorted(Order.browse(order.ids).line_ids.ids) == sorted(
        [keep.id, moved.id])
    assert not Line.browse(drop.ids).exists()
    assert not Order.browse(other.ids).line_ids
