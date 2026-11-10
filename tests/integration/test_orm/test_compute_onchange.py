"""Cómputos almacenados editables y x2many calculados — porte de
``TestComputeOnchange2`` y de los atributos de ``test_orm.compute.onchange``.

Referencia: odoo-tools ``abe4040ec1``,
``odoo19c: odoo/addons/test_orm/tests/test_onchange.py:958-1120``,
``…/tests/test_fields.py:114-131`` y el modelo
``…/models/test_orm.py:880-950``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
many2many-write-family.md``.

``test_copy_batch`` (``test_onchange.py:1013-1024``) no se porta todavía:
necesita ``test_orm.partner`` y ``assertQueryCount``; queda pendiente en el
diseño.
"""
import pytest
from django.db import connection

import fields

pytestmark = pytest.mark.django_db


def test_stored_editable_computed_field_attributes(env):
    """≙ ``test_fields.py:114-131``."""
    model = env['test_orm.compute.onchange']
    field = model._fields['baz']
    assert field.store and field.compute_sudo and not field.readonly
    assert field.copy

    field = model._fields['line_ids']
    assert field.store and field.compute_sudo and not field.readonly
    assert not field.copy  # like a regular one2many field

    field = model._fields['tag_ids']
    assert field.store and field.compute_sudo and not field.readonly
    assert field.copy  # like a regular many2many field


def test_create(env):
    model = env['test_orm.compute.onchange']

    # compute 'bar' (readonly) and 'baz' (editable)
    record = model.create({'active': True})
    assert record.bar == "r"
    assert record.baz == "z"

    # compute 'bar' and 'baz'
    record = model.create({'active': True, 'foo': "foo"})
    assert record.bar == "foor"
    assert record.baz == "fooz"

    # compute 'bar' but not 'baz'
    record = model.create({'active': True, 'foo': "foo", 'bar': "bar",
                           'baz': "baz"})
    assert record.bar == "foor"
    assert record.baz == "baz"

    # compute 'bar' and 'baz', but do not change its value
    record = model.create({'active': False, 'foo': "foo"})
    assert record.bar == "foor"
    assert not record.baz

    # compute 'bar' but not 'baz'
    record = model.create({'active': False, 'foo': "foo", 'bar': "bar",
                           'baz': "baz"})
    assert record.bar == "foor"
    assert record.baz == "baz"


def test_copy(env):
    Model = env['test_orm.compute.onchange']

    # create tags
    tag_foo, tag_bar = env['test_orm.multi.tag'].create([
        {'name': 'foo1'},
        {'name': 'bar1'},
    ])

    # compute 'bar' (readonly), 'baz', 'line_ids' and 'tag_ids' (editable)
    record = Model.create({'active': True, 'foo': "foo1"})
    assert record.bar == "foo1r"
    assert record.baz == "foo1z"
    assert record.line_ids.mapped('foo') == ['foo1']
    assert record.tag_ids == tag_foo

    # manually update 'baz' and 'lines' to test copy attribute
    record.write({
        'baz': "baz1",
        'line_ids': [fields.Command.create({'foo': 'bar'})],
        'tag_ids': [fields.Command.link(tag_bar.id)],
    })
    assert record.bar == "foo1r"
    assert record.baz == "baz1"
    assert record.line_ids.mapped('foo') == ['foo1', 'bar']
    assert record.tag_ids == tag_foo + tag_bar

    # copy the record, and check results
    copied = record.copy()
    assert copied.foo == "foo1 (copy)"   # copied and modified
    assert copied.bar == "foo1 (copy)r"  # computed
    assert copied.baz == "baz1"          # copied
    assert record.line_ids.mapped('foo') == ['foo1', 'bar']  # copied
    assert record.tag_ids == tag_foo + tag_bar  # copied


def test_write(env):
    model = env['test_orm.compute.onchange']
    record = model.create({'active': True, 'foo': "foo"})
    assert record.bar == "foor"
    assert record.baz == "fooz"

    # recompute 'bar' (readonly) and 'baz' (editable)
    record.write({'foo': "foo1"})
    assert record.bar == "foo1r"
    assert record.baz == "foo1z"

    # recompute 'bar' but not 'baz'
    record.write({'foo': "foo2", 'bar': "bar2", 'baz': "baz2"})
    assert record.bar == "foo2r"
    assert record.baz == "baz2"

    # recompute 'bar' and 'baz', but do not change its value
    record.write({'active': False, 'foo': "foo3"})
    assert record.bar == "foo3r"
    assert record.baz == "baz2"

    # recompute 'bar' but not 'baz'
    record.write({'active': False, 'foo': "foo4", 'bar': "bar4",
                  'baz': "baz4"})
    assert record.bar == "foo4r"
    assert record.baz == "baz4"


def test_set(env):
    model = env['test_orm.compute.onchange']
    record = model.create({'active': True, 'foo': "foo"})
    assert record.bar == "foor"
    assert record.baz == "fooz"

    # recompute 'bar' (readonly) and 'baz' (editable)
    record.foo = "foo1"
    assert record.bar == "foo1r"
    assert record.baz == "foo1z"

    # do not recompute 'baz'
    record.baz = "baz2"
    assert record.bar == "foo1r"
    assert record.baz == "baz2"

    # recompute 'baz', but do not change its value
    record.active = False
    assert record.bar == "foo1r"
    assert record.baz == "baz2"

    # recompute 'baz', but do not change its value
    record.foo = "foo3"
    assert record.bar == "foo3r"
    assert record.baz == "baz2"

    # do not recompute 'baz'
    record.baz = "baz4"
    assert record.bar == "foo3r"
    assert record.baz == "baz4"


def test_set_new(env):
    model = env['test_orm.compute.onchange']
    record = model.new({'active': True})
    assert record.bar == "r"
    assert record.baz == "z"

    # recompute 'bar' (readonly) and 'baz' (editable)
    record.foo = "foo1"
    assert record.bar == "foo1r"
    assert record.baz == "foo1z"

    # do not recompute 'baz'
    record.baz = "baz2"
    assert record.bar == "foo1r"
    assert record.baz == "baz2"

    # recompute 'baz', but do not change its value
    record.active = False
    assert record.bar == "foo1r"
    assert record.baz == "baz2"

    # recompute 'baz', but do not change its value
    record.foo = "foo3"
    assert record.bar == "foo3r"
    assert record.baz == "baz2"

    # do not recompute 'baz'
    record.baz = "baz4"
    assert record.bar == "foo3r"
    assert record.baz == "baz4"


# --- el despacho relacional del Many2many ----------------------------------

def _tags_in_database(record):
    table = 'test_orm_compute_onchange_test_orm_multi_tag_rel'
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT test_orm_multi_tag_id FROM {table}'
            ' WHERE test_orm_compute_onchange_id = %s ORDER BY 1',
            [record.id])
        return [row[0] for row in cursor.fetchall()]


def _relation_rows():
    with connection.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM '
                       'test_orm_compute_onchange_test_orm_multi_tag_rel')
        return cursor.fetchone()[0]


def test_setitem_on_a_record_being_computed_writes_the_relation(env):
    """``BaseModel.__setitem__`` (≙ ``Field.__set__``, ``fields.py:1820-
    1823``) sobre una fila en cómputo llama ``field.write``; en un
    ``Many2many`` la fuente despacha por ``write_batch`` → ``write_real``
    (``fields_relational.py:737-764``, ``:1413``), no por la escritura de un
    escalar."""
    model = env['test_orm.compute.onchange']
    record = model.create({'foo': 'none'})
    tag = env['test_orm.multi.tag'].create({'name': 'protected'})
    field = model._fields['tag_ids']
    with env.protecting([field], record):
        record['tag_ids'] = tag
    assert _tags_in_database(record) == [tag.id]
    assert record.tag_ids == tag


def test_many2many_write_family(env):
    """``write``/``write_batch``/``write_real`` del ``Many2many`` con las
    formas de valor de ``write_batch`` (``:742-764``)."""
    model = env['test_orm.compute.onchange']
    field = model._fields['tag_ids']
    record = model.create({'foo': 'none'})
    one, two = env['test_orm.multi.tag'].create([{'name': 'a'},
                                                 {'name': 'b'}])
    field.write(record, [fields.Command.link(one.id)])
    assert _tags_in_database(record) == [one.id]
    field.write_batch([(record, (two.id,))])
    assert _tags_in_database(record) == [two.id]
    field.write_batch([(record, False)])
    assert _tags_in_database(record) == []
    field.write_batch([(record, one + two)])
    assert _tags_in_database(record) == sorted([one.id, two.id])
    with pytest.raises(ValueError, match='Wrong value for'):
        field.write_batch([(record, 'nope')])


def test_many2many_write_new_stays_in_cache(env):
    """``Many2many.write_new`` (``:1596-1700``): un registro de ``new()``
    sólo cambia la caché; nada va a la tabla intermedia."""
    model = env['test_orm.compute.onchange']
    field = model._fields['tag_ids']
    tag = env['test_orm.multi.tag'].create({'name': 'n'})
    rows_before = _relation_rows()
    record = model.new({'foo': 'none'})
    field.write_batch([(record, [fields.Command.link(tag.id)])])
    # el valor de un registro nuevo son registros nuevos (``NewId(id)``)
    assert [line._origin.id for line in record.tag_ids] == [tag.id]
    assert not record.tag_ids.id
    assert not record.id
    assert _relation_rows() == rows_before
    seeded = model.new({'foo': 'none',
                        'tag_ids': [fields.Command.set([tag.id])]})
    assert [line._origin.id for line in seeded.tag_ids] == [tag.id]


def test_many2many_write_batch_accepts_the_comodel_queryset(env):
    """Rama de ``write_batch`` para el ``QuerySet`` de Django: es el conjunto
    de filas del comodelo, el mismo papel que el recordset de ``:744``, y se
    normaliza a ``Command.set`` de sus claves."""
    model = env['test_orm.compute.onchange']
    field = model._fields['tag_ids']
    record = model.create({'foo': 'none'})
    one, two = env['test_orm.multi.tag'].create([{'name': 'qs-a'},
                                                 {'name': 'qs-b'}])
    queryset = env['test_orm.multi.tag'].objects.filter(
        pk__in=[one.id, two.id])
    field.write_batch([(record, queryset)])
    assert _tags_in_database(record) == sorted([one.id, two.id])


def test_protected_assignment_skips_the_model_write(env, monkeypatch):
    """``Field.__set__`` (``fields.py:1820-1823``): sobre una fila en
    cómputo se escribe *sin lógica de negocio* — ``field.write``, nunca el
    ``write`` del modelo, que anuncia, valida y recalcula."""
    model = env['test_orm.compute.onchange']
    record = model.create({'foo': 'none'})
    tag = env['test_orm.multi.tag'].create({'name': 'no-business'})
    calls = []
    original_write = type(record).write

    def spy_write(self, vals):
        calls.append(vals)
        return original_write(self, vals)

    monkeypatch.setattr(type(record), 'write', spy_write)
    with env.protecting([model._fields['tag_ids']], record):
        record.tag_ids = tag
    assert calls == []
    assert _tags_in_database(record) == [tag.id]
