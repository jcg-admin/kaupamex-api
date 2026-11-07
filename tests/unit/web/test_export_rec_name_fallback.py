"""El nombre del registro relacionado en la exportación compatible.

≙ ``odoo19c: addons/web/controllers/export.py:378-380``: con
``import_compat`` y un padre ``many2one``/``many2many``, el árbol de campos se
reduce a ``id`` y al campo que devuelve ``Model._rec_name_fallback()``, que es
``_rec_name or 'id'`` (``odoo/orm/models.py:1340-1343``). La referencia no
tiene la heurística del primer ``CharField`` que el controlador del puerto
aplicaba (H-API-1162, TASK-API-0499).

``test_orm.mixed`` no tiene ``_rec_name`` y sí un ``CharField`` (``foo``): la
referencia reduce el árbol a ``id``; la heurística lo reducía a ``id`` y
``foo``. ``test_orm.category`` resuelve ``_rec_name`` a ``name``.
"""

import pytest

from addons.test_orm.models.test_orm import (
    TestOrmMixed,
    TestOrmModelActiveField,
)
from addons.web.controllers.export import get_fields

pytestmark = pytest.mark.django_db


def _names(model):
    return sorted(entry['id'] for entry in get_fields(
        model, [], import_compat=True, parent_field_type='many2one'))


def test_a_model_without_rec_name_keeps_only_the_id():
    assert _names(TestOrmMixed) == ['id']


def test_a_model_with_rec_name_keeps_it():
    assert _names(TestOrmModelActiveField) == ['id', 'name']
