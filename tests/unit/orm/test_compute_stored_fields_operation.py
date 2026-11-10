"""Una migración calcula los calculados almacenados que añade.

≙ ``odoo19c: odoo/orm/models.py:3220-3238`` (``_auto_init`` marca para
cómputo las filas existentes de una columna calculada nueva). Diseño en
``designs/compute-new-stored-columns.md`` del Workbench (TASK-API-0516).

*Métrica:* el valor en la base de las columnas tras ejecutar la operación,
leído con SQL: la lectura por el ORM devuelve el valor de la caché de la
transacción aunque la columna esté en ``NULL``.
*Ciega a:* el orden entre varias operaciones de una misma migración.
"""
import pytest
from django.apps import apps
from django.db import connection

from orm.environments import Environment
from orm.migration_operations import ComputeStoredFields
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def child(db):
    with Environment(None, SUPERUSER_ID, {}) as env:
        parent = env['test_orm.model_parent_m2o'].create({'name': 'pqrs'})
        record = env['test_orm.model_child_m2o'].create(
            {'name': 'c', 'parent_id': parent.id, 'cost': 2})
        record.flush_model()
    model = type(record)
    model.objects.filter(pk=record.id).update(size1=None, size2=None)
    return model, record.id


def _stored(record_id):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT size1, size2 FROM test_orm_model_child_m2o WHERE id = %s',
            [record_id])
        return cursor.fetchone()


def _run(operation):
    with connection.schema_editor() as editor:
        operation.code(apps, editor)


def test_existing_rows_get_their_computed_value(child):
    model, record_id = child
    assert _stored(record_id) == (None, None)
    _run(ComputeStoredFields('test_orm', 'testormmodelchildm2o', ['size1']))
    assert _stored(record_id)[0] == 4


def test_fields_of_one_compute_are_filled_together(child):
    model, record_id = child
    _run(ComputeStoredFields(
        'test_orm', 'testormmodelchildm2o', ['size1', 'size2']))
    assert _stored(record_id) == (4, 4)


def test_an_empty_table_is_a_no_op(db):
    _run(ComputeStoredFields('test_orm', 'testormmodelparentm2o', ['cost']))
