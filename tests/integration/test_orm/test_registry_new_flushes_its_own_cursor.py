"""Construir un registro vuelca en SU cursor, no en el de quien lo pide.

≙ ``load_modules`` (``odoo19c: odoo/modules/loading.py:340-595``): el
volcado del paso 9 es el de ``Environment(cr, SUPERUSER_ID, {})`` sobre el
cursor que ``Registry.new`` abre. Con el entorno activo, construir el
registro volcaba las marcas pendientes del llamador; en una prueba sin base
eso intentaba escribir una fila que sólo existía en memoria.
"""
import pytest
from django.apps import apps

from orm.environments import get_transaction
from orm.registry import Registry
from tests.conftest import preserved_registries

pytestmark = pytest.mark.django_db

SharedCompute = apps.get_model('test_orm', 'TestOrmSharedCompute')


def _pending(record_id):
    return {field.name
            for field, ids in get_transaction().tocompute.items()
            if getattr(field, 'model', None) is SharedCompute
            and record_id in ids}


def test_building_a_registry_leaves_the_callers_marks_pending():
    row = SharedCompute.objects.create(name='1->2')
    assert _pending(row.pk) == {'start', 'end'}
    with preserved_registries():
        Registry.new('default')
    assert _pending(row.pk) == {'start', 'end'}


def test_a_new_registry_starts_from_the_database_signaling():
    """≙ ``registry.setup_signaling()`` en ``Registry.new``
    (``odoo19c: odoo/orm/registry.py:159``): el registro nace con las
    secuencias de su base, así que ``check_signaling`` no lo reconstruye."""
    with preserved_registries():
        built = Registry.new('default')
        assert built.registry_sequence != -1
        assert built.check_signaling() is built


def test_a_base_without_its_signaling_tables_builds_unsignaled(monkeypatch):
    """Una base aún sin ``base.0085`` (``--create-db`` antes de ``migrate``).

    La fuente crearía ahí las tablas; aquí las crea la migración, así que
    el registro nace sin señalizar en vez de fallar (ci-multidb de
    ``fd324cca``: 15 errores de fixture con ``RuntimeError``).
    """
    monkeypatch.setattr('orm.registry.signaling_table_names',
                        lambda: ('orm_signaling_not_migrated',))
    with preserved_registries():
        built = Registry.new('default')
        assert built.registry_sequence == -1
