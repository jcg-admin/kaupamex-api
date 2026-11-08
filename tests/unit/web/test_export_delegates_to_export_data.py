"""La exportación de web delega en ``export_data`` del modelo.

≙ ``ExportFormat.base`` (``odoo19c: addons/web/controllers/export.py:
554-620``): los registros se buscan en el modelo con ``import_compat`` en el
contexto, y las filas salen de ``records.export_data(field_names)``, por lotes
de ``PREFETCH_MAX``. El puerto armaba las filas con un recorrido propio, que
no sabe la columna ``id``: la referencia exporta ahí el identificador externo
(``__export__.<tabla>_<id>_<uuid>``, ``odoo/orm/models.py:599-676``) y el
recorrido local, la clave primaria.

Un modelo de Django sin ``export_data`` sigue por el recorrido local.
"""
import csv
import io

import pytest

from addons.test_orm.models.test_orm import TestOrmDiscussion
from addons.web.controllers.export import CSVExport
from orm.environments import sudo

pytestmark = pytest.mark.django_db


def _rows(model, ids, names):
    payload = {
        'model': f'{model._meta.app_label}.{model._meta.object_name}',
        'fields': [{'name': name, 'label': name} for name in names],
        'ids': ids, 'domain': [], 'import_compat': True,
    }
    response = CSVExport().base(payload)
    return list(csv.reader(io.StringIO(response.content.decode())))[1:]


def test_the_id_column_is_the_external_id():
    with sudo():
        discussion = TestOrmDiscussion.browse(()).create(
            {'name': 'exportada'})
        rows = _rows(TestOrmDiscussion, [discussion.id], ['name', 'id'])
    assert rows[0][0] == 'exportada'
    assert rows[0][1].startswith('__export__.test_orm_discussion_')
