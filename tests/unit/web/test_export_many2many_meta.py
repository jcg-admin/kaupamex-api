"""La metadata de un ``Many2many`` directo en el árbol de exportación.

En la referencia, ``Export.get_fields`` lee ``Model.fields_get``
(``odoo19c: addons/web/controllers/export.py:368-375``), que describe un
``Many2many`` declarado como ``type='many2many'`` con su modelo de destino en
``relation`` y sin ``readonly``: se escribe desde el modelo que lo declara.
El puerto mandaba el ``ManyToManyField`` directo a la rama del inverso,
porque tampoco es concreto, y reventaba en ``get_accessor_name``
(H-API-1163, TASK-API-0500).

``test_orm.category`` declara ``discussions`` y
``test_orm.model_active_field`` declara ``relatives_ids``.
"""

import pytest

from addons.test_orm.models.test_orm import (
    TestOrmCategory,
    TestOrmModelActiveField,
)
from addons.web.controllers.export import get_fields

pytestmark = pytest.mark.django_db


def _entry(model, name):
    entries = get_fields(model, [], import_compat=False)
    return next(entry for entry in entries if entry['id'] == name)


@pytest.mark.parametrize('model, name', [
    (TestOrmCategory, 'discussions'),
    (TestOrmModelActiveField, 'relatives_ids'),
])
def test_a_direct_many2many_is_described_as_many2many(model, name):
    entry = _entry(model, name)
    assert entry['field_type'] == 'many2many'
    assert entry['children'] is True
