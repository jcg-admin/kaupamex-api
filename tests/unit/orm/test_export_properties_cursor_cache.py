"""La caché de propiedades de ``_export_rows`` vive en ``env.cr.cache``.

≙ ``odoo19c: odoo/orm/models.py:686-694`` y ``:875-876``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
export-properties-cursor-cache.md``.

*Métrica:* la clave ``export_properties_cache`` de ``env.cr.cache`` durante
la llamada recursiva y después de la de primer nivel.
*Ciega a:* el contenido de la caché, que miden las pruebas de ``Properties``.
"""
import pytest

from orm.environments import env, sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

KEY = 'export_properties_cache'


@pytest.fixture
def plans():
    with sudo():
        model = env()['account.analytic.plan']
        root = model.create({'name': 'Raíz exportada'})
        child = model.create({'name': 'Hijo exportado',
                              'parent_id': root.id})
        yield child


def test_the_recursive_call_reads_the_cursor_cache(plans, monkeypatch):
    original = BaseModel._export_rows
    seen = []

    def spy(self, fields, *, _is_toplevel_call=True):
        if not _is_toplevel_call:
            seen.append(env().cr.cache.get(KEY))
        return original(self, fields, _is_toplevel_call=_is_toplevel_call)

    monkeypatch.setattr(BaseModel, '_export_rows', spy)
    with sudo():
        plans.export_data(['name', 'parent_id/name'])
    assert seen and all(cache is not None for cache in seen)
    assert all(cache is seen[0] for cache in seen)


def test_the_toplevel_call_drops_it(plans):
    with sudo():
        rows = plans.export_data(['name', 'parent_id/name'])['datas']
    assert rows == [['Hijo exportado', 'Raíz exportada']]
    assert KEY not in env().cr.cache
