"""``index=`` de la referencia llega a la base como índice btree.

≙ ``Field.index`` (``odoo19c: odoo/orm/fields.py:279``) y la rama btree de
``Registry.check_indexes`` (``odoo/orm/registry.py:831-880``): ``True`` y
``'btree'`` piden un índice btree sobre la columna. Aquí ``check_indexes`` no
corre sobre un esquema migrado, así que la costura traduce a ``db_index``.
Diseño en ``designs/field-index-to-db-index.md`` del Workbench.

*Métrica:* ``db_index`` del campo construido y los índices de la tabla en
``pg_indexes``.
*Ciega a:* el nombre del índice, que es el de Django (divergencia declarada).
"""
import pytest
from django.db import connection

import fields
from orm.registry import MODELS_BY_NAME


@pytest.mark.parametrize('index', [True, 'btree'])
def test_a_btree_index_becomes_db_index(index):
    assert fields.Char(index=index, null=True).db_index is True


@pytest.mark.parametrize('index', [None, False, 'btree_not_null', 'trigram'])
def test_other_values_do_not_ask_for_a_plain_index(index):
    """CONTROL: el índice parcial y el trigram no son un btree llano."""
    assert fields.Char(index=index, null=True).db_index is False


@pytest.mark.django_db
@pytest.mark.parametrize('model_name, column', [
    ('res.partner', 'ref'),
    ('test_orm.category', 'parent_path'),
])
def test_the_migrated_table_carries_the_index(model_name, column):
    table = MODELS_BY_NAME[model_name]._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s", [table])
        definitions = [row[0] for row in cursor.fetchall()]
    assert any(f'({column})' in definition for definition in definitions)
