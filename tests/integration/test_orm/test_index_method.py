"""Porte de ``odoo19c: odoo/addons/test_orm/tests/test_index_method.py``.

Revisión de referencia: ``odoo-tools@abe4040ec1``. Docstring de la fuente,
verbatim: *"``Registry.check_indexes`` must rebuild a column index when the
field changes the kind of index it wants (e.g. btree -> trigram), even though
the index name stays the same."*

**Adaptación declarada:** la fuente usa ``res.partner.ref``
(``odoo19c: odoo/addons/base/models/res_partner.py:218``,
``fields.Char(string='Reference', index=True)``). Ese campo no existe todavía
en el ``res.partner`` del Consumer, así que el caso se ejerce sobre
``test_orm.category.parent_path``, que es un ``Char`` con ``index=True`` en el
mismo addon de prueba de la fuente.
"""

import pytest
from django.db import connection

from orm.registry import Registry
from tools import sql

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def registry(db):
    Registry.delete_all()
    built = Registry('default')
    yield built
    Registry.delete_all()


@pytest.fixture
def cr(db):
    with connection.cursor() as cursor:
        yield cursor


def _index_method(cr, indexname):
    cr.execute(
        """
        SELECT am.amname
          FROM pg_class idx
          JOIN pg_am am ON am.oid = idx.relam
         WHERE idx.relname = %s
        """,
        [indexname],
    )
    row = cr.fetchone()
    return row[0] if row else None


def test_index_rebuilt_when_method_changes(registry, cr):
    if not registry.has_trigram:
        pytest.skip("pg_trgm extension is required for trigram indexes")

    model = registry['test_orm.category']
    field = model._fields['parent_path']
    indexname = sql.make_index_name(model._table, 'parent_path')

    # El estado de una base actualizada: la columna lleva un btree con el
    # nombre de la convención y el campo pide ahora un trigram.
    sql.drop_index(cr, indexname, model._table)
    sql.create_index(cr, indexname, model._table, ['"parent_path"'], 'btree')
    assert _index_method(cr, indexname) == 'btree'

    original_index = field.index
    field.index = 'trigram'
    try:
        registry.check_indexes(cr, ['test_orm.category'])
    finally:
        field.index = original_index

    # El btree obsoleto se retira y se rehace como gin/trigram con el mismo
    # nombre.
    assert _index_method(cr, indexname) == 'gin'
