"""``invalidate_recordset`` también deja sin valor la copia de la instancia.

≙ ``odoo19c: odoo/orm/models.py:6724-6736`` («Invalidate the cache of the
records in ``self``, when the cached values no longer correspond to the
database values») y ``odoo/orm/fields.py:1642-1700``: tras invalidar, la
lectura falla en caché y va a la base. Aquí la instancia de Django guarda su
copia en ``__dict__``; si sobrevive a la invalidación, la fila invalidada lee
su valor viejo. Diseño: ``scripts/workbench/orm-continuation-plan-
20261103T095630/designs/stale-instance-snapshot.md``.
"""
import pytest
from django.db import connection

from orm.environments import sudo
from orm.registry import MODELS_BY_NAME

pytestmark = [pytest.mark.unit, pytest.mark.django_db]
PARENT = 'test_orm.model_parent_m2o'


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _update_behind_the_orm(record, column, value):
    with connection.cursor() as cursor:
        cursor.execute(
            f'UPDATE {type(record)._meta.db_table} SET {column} = %s '
            'WHERE id = %s', [value, record.id])


def test_a_plain_stored_field_reads_the_database_after_invalidation():
    [record] = MODELS_BY_NAME[PARENT].create([{'name': 'antes'}])
    record.flush_recordset()
    assert record.name == 'antes'
    _update_behind_the_orm(record, 'name', 'despues')
    record.invalidate_recordset(['name'])
    assert record.name == 'despues'


def test_a_stored_computed_field_reads_the_database_after_invalidation():
    [created] = MODELS_BY_NAME[PARENT].create([{'name': 'padre'}])
    created.flush_recordset()
    # Cargada de la base, la instancia lleva ``cost`` en su ``__dict__``,
    # como la línea de compra del episodio de origen.
    record = type(created).objects.get(pk=created.id)
    assert record.cost == 0
    _update_behind_the_orm(record, 'cost', 7)
    record.invalidate_recordset(['cost'])
    assert record.cost == 7


def test_without_invalidation_the_cached_value_stays():
    """Control: sin invalidar, la fuente sigue leyendo su caché, y aquí la
    copia — leer la base en cada acceso no es el contrato."""
    [record] = MODELS_BY_NAME[PARENT].create([{'name': 'antes'}])
    record.flush_recordset()
    assert record.name == 'antes'
    _update_behind_the_orm(record, 'name', 'despues')
    assert record.name == 'antes'


def test_another_instance_of_an_invalidated_row_is_refreshed_too():
    """La fuente no tiene copias: toda instancia de la fila deja de tener
    valor al invalidarla, también la que no recibió la llamada."""
    [record] = MODELS_BY_NAME[PARENT].create([{'name': 'antes'}])
    record.flush_recordset()
    other = type(record).objects.get(pk=record.id)
    assert other.name == 'antes'
    _update_behind_the_orm(record, 'name', 'despues')
    record.invalidate_recordset(['name'])
    assert other.name == 'despues'
