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
