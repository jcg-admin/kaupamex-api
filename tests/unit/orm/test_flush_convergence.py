"""El volcado converge tras escribir una fila con fecha ``auto_now``.

``Environment.flush_all`` (``odoo19c: odoo/orm/environments.py:380-390``)
repite cómputo y volcado hasta que ``_field_dirty`` queda vacío, con un tope
de ``MAX_FIXPOINT_ITERATIONS`` vueltas tras el que avisa *"Too many
iterations for flushing fields!"*. Allá ``_flush`` saca (``pop``) los ids
que escribe (``models.py:6386-6400``) y nada los vuelve a marcar.

Aquí la escritura la hace ``Model.save`` de Django, y su ``pre_save`` de un
campo ``auto_now`` asigna la fecha con ``setattr`` *dentro* de ese mismo
guardado. La asignación pasaba por ``FieldDescriptor.__set__`` →
``field.write`` y volvía a marcar sucio ``write_date``, que ya iba en el
``UPDATE``: cada vuelta lo recreaba y el volcado agotaba el tope.

*Métrica:* ids sucios tras ``flush_all`` y el aviso del logger.
*Ciega a:* otros ``pre_save`` que asignan (``FileField``) sin modelo de
prueba aquí.
"""
import logging

import pytest

from orm.environments import env as current_env
from orm.environments import sudo
from orm.registry import MODELS_BY_NAME
from orm.utils import model_field_registry

pytestmark = pytest.mark.django_db

WARNING = 'Too many iterations for flushing fields!'


def _dirty(e):
    return {field.name: sorted(ids)
            for field, ids in e._field_dirty.items() if ids}


@pytest.fixture
def related():
    with sudo():
        e = current_env()
        foo = e['test_orm.related_foo'].create({'name': 'foo'})
        record = e['test_orm.related'].create({'name': 'r',
                                               'foo_id': foo.id})
        e.flush_all()
        yield e, record


def test_write_then_flush_leaves_nothing_dirty(related, caplog):
    e, record = related
    with sudo():
        record.write({'name': 'renamed'})
        with caplog.at_level(logging.WARNING, logger='orm.environments'):
            e.flush_all()
        assert _dirty(e) == {}
    assert WARNING not in caplog.text


def test_the_written_date_is_the_persisted_one(related):
    e, record = related
    with sudo():
        record.write({'name': 'renamed'})
        e.flush_all()
        row = MODELS_BY_NAME['test_orm.related']._base_manager.get(
            pk=record.id)
        assert row.write_date == record.write_date
        assert row.name == 'renamed'


def test_a_dirty_value_not_written_stays_dirty(related):
    """Control: la limpieza sólo alcanza lo que el ``save`` escribió."""
    e, record = related
    field = model_field_registry(type(record))['name']
    with sudo():
        field._update_cache([record], 'pending', dirty=True)
        record.save(update_fields=['write_date'])
        assert _dirty(e).get('name') == [record.id]
        e.flush_all()
        assert _dirty(e) == {}
        row = MODELS_BY_NAME['test_orm.related']._base_manager.get(
            pk=record.id)
        assert row.name == 'pending'


def test_a_written_column_with_another_cached_value_stays_dirty(related):
    """Guarda de valor: la columna se escribe, pero con el valor de la fila y
    no con el de la caché, así que lo de la caché sigue pendiente."""
    e, record = related
    field = model_field_registry(type(record))['name']
    with sudo():
        field._update_cache([record], 'pending', dirty=True)
        record.save(update_fields=['name'])
        assert _dirty(e).get('name') == [record.id]


def test_an_unwritten_column_with_the_same_value_stays_dirty(related):
    """Guarda de ``update_fields``: la fila lleva el valor de la caché pero el
    ``save`` no escribe esa columna, así que no se persistió."""
    e, record = related
    field = model_field_registry(type(record))['name']
    with sudo():
        field._update_cache([record], 'pending', dirty=True)
        record.__dict__['name'] = 'pending'
        record.save(update_fields=['write_date'])
        assert _dirty(e).get('name') == [record.id]
