"""Lectura de un ``Many2one`` calculado sin columna sobre varios registros.

≙ el caso de varios registros de ``_Relational.__get__`` (``odoo19c:
odoo/orm/fields_relational.py:42-79``), que une los corecords leídos de la
caché con ``convert_to_record_multi``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
read-nonstored-many2one-multi.md``.

*Métrica:* el tipo y los ids de ``mapped`` sobre el campo.
*Ciega a:* los ``Many2one`` almacenados, que leen su fila por otra rama.
"""
import pytest

from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _superuser():
    with sudo():
        yield


def test_mapped_over_a_nonstored_many2one_gives_the_corecords():
    categories = env()['test_orm.category']
    [root] = categories.create([{'name': 'Raíz'}])
    [child, other] = categories.create([
        {'name': 'Hija', 'parent': root.id},
        {'name': 'Otra'},
    ])
    found = (child | other).mapped('root_categ')
    assert found._name == 'test_orm.category'
    assert found == root | other


def test_a_single_record_still_reads_its_corecord():
    categories = env()['test_orm.category']
    [root] = categories.create([{'name': 'Raíz'}])
    [child] = categories.create([{'name': 'Hija', 'parent': root.id}])
    assert child.root_categ == root
