"""``BaseModel._write``, ``_write_multi`` y el volcado de ``_flush``.

≙ ``odoo19c: odoo/orm/models.py:4520-4608`` y ``:6386-6432``. Diseño en
``designs/write-multi-flush.md`` del Workbench (TASK-API-0510).

*Métrica:* las filas en la base tras la escritura, las llamadas que ve un
espía sobre ``_write_multi`` y los argumentos de ``post_save``.
*Ciega a:* la forma del enunciado SQL — aquí es ``save(update_fields)`` por
fila, divergencia declarada en el diseño.
"""
import datetime

import pytest
from django.db.models.signals import post_save

from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

PAST = datetime.datetime(2001, 1, 1, tzinfo=datetime.UTC)


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


@pytest.fixture
def family(env):
    parent = env['test_orm.model_parent_m2o'].create({'name': 'p'})
    child = env['test_orm.model_child_m2o'].create(
        {'name': 'c', 'parent_id': parent.id, 'cost': 2})
    child.flush_model()
    return parent, child


def _stamp(record):
    return type(record).objects.filter(pk=record.id).values_list(
        'write_date', flat=True).get()


def _age(record):
    type(record).objects.filter(pk=record.id).update(write_date=PAST)


def test_write_multi_rejects_a_length_mismatch(env):
    Category = env['test_orm.category']
    records = Category.create({'name': 'a'}) | Category.create({'name': 'b'})
    with pytest.raises(AssertionError):
        records._write_multi([{'name': 'x'}])


def test_write_multi_on_nothing_returns_none(env):
    assert env['test_orm.category'].browse(())._write_multi([]) is None


def test_write_applies_the_same_values_to_each_record(env):
    Category = env['test_orm.category']
    records = Category.create({'name': 'a'}) | Category.create({'name': 'b'})
    records._write({'name': 'same'})
    names = set(type(records).objects.filter(
        pk__in=records.ids).values_list('name', flat=True))
    assert names == {'same'}


def test_write_multi_rewrites_the_parent_path(env):
    Category = env['test_orm.category']
    root_a = Category.create({'name': 'a'})
    root_b = Category.create({'name': 'b'})
    child = Category.create({'name': 'c', 'parent': root_a.id})
    leaf = Category.create({'name': 'l', 'parent': child.id})
    child._write_multi([{'parent': root_b.id}])
    path = type(leaf).objects.filter(pk=leaf.id).values_list(
        'parent_path', flat=True).get()
    assert path == f'{root_b.id}/{child.id}/{leaf.id}/'


def test_write_multi_dates_the_record(env):
    record = env['test_orm.category'].create({'name': 'a'})
    _age(record)
    record._write_multi([{'name': 'b'}])
    assert _stamp(record) > PAST


def test_flush_goes_through_write_multi(env, family, monkeypatch):
    parent, child = family
    model = type(child)
    calls = []
    original = model._write_multi

    def spy(self, vals_list):
        calls.append((tuple(self.ids), [dict(v) for v in vals_list]))
        return original(self, vals_list)

    monkeypatch.setattr(model, '_write_multi', spy)
    parent.write({'name': 'pqrs'})
    child.flush_model()
    assert ((child.id,), [{'size1': 4, 'size2': 4}]) in calls


def test_flushing_a_computed_field_dates_the_record(env, family):
    parent, child = family
    _age(child)
    parent.write({'name': 'pqrs'})
    child.flush_model()
    assert type(child).objects.get(pk=child.id).size1 == 4
    assert _stamp(child) > PAST


def test_post_save_still_receives_the_flush(env, family):
    parent, child = family
    seen = []

    def receiver(sender, instance, update_fields=None, **kwargs):
        if instance.pk == child.id:
            seen.append(set(update_fields or ()))

    post_save.connect(receiver, sender=type(child), weak=False)
    try:
        parent.write({'name': 'pqrs'})
        child.flush_model()
    finally:
        post_save.disconnect(receiver, sender=type(child))
    assert any('size1' in fields for fields in seen)
