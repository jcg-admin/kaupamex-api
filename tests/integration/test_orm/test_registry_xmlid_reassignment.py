"""El registro de una unidad de trabajo es el de su base, y la reasignación
de un xml-id se anota, se siembra y se deshace en ese registro.

≙ ``Transaction(Registry(cr.dbname))``
(``odoo19c: odoo/orm/environments.py:72``) y ``_update_xmlids``
(``odoo/addons/base/models/ir_model.py:2367-2412``). Las unidades corren con el
cursor real, fuera del ``TestCase``: la reasignación sólo distingue
``create_date`` de ``write_date`` entre dos transacciones, y una prueba es una
sola. Cada caso retira lo que confirmó.
"""
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_module import IrModuleCategory
from orm import registry as orm_registry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tests.conftest import REAL_REGISTRY_CURSOR

XMLID = 'probe_caches.category'


@pytest.fixture(autouse=True)
def _unblocked(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        yield


def _cursor():
    return REAL_REGISTRY_CURSOR(orm_registry.Registry('default'), False)


@pytest.fixture
def categories():
    with _cursor() as cr:
        env = Environment(cr.alias, SUPERUSER_ID, {})
        with env:
            first = IrModuleCategory.objects.using(cr.alias).create(
                name='probe first')
            second = IrModuleCategory.objects.using(cr.alias).create(
                name='probe second')
    yield first.pk, second.pk
    with _cursor() as cr:
        cr.execute("DELETE FROM ir_model_data WHERE module = 'probe_caches'")
        cr.execute('DELETE FROM ir_module_category WHERE id = ANY(%s)',
                   [[first.pk, second.pk]])


def _assign(pk):
    """Una unidad de trabajo que asigna el xml-id a la categoría ``pk``."""
    with _cursor() as cr, Environment(cr.alias, SUPERUSER_ID, {}):
        record = IrModuleCategory.objects.using(cr.alias).get(pk=pk)
        IrModelData._update_xmlids(
            [{'xml_id': XMLID, 'record': record}], using=cr.alias)
        return IrModelData._xmlid_lookup(XMLID, using=cr.alias)


def test_the_environment_of_a_cursor_uses_the_registry_of_its_database():
    base = orm_registry.Registry('default')
    with _cursor() as cr:
        assert Environment(cr.alias, SUPERUSER_ID, {}).registry is base
        assert cr.alias not in orm_registry.Registry.registries


def test_moving_an_xmlid_marks_its_database_registry(categories):
    first, second = categories
    base = orm_registry.Registry('default')
    _assign(first)
    base.cache_invalidated.clear()
    model, res_id = _assign(second)
    assert (model, res_id) == ('base.IrModuleCategory', second)
    assert 'default' in base.cache_invalidated


def test_assigning_the_same_target_again_changes_nothing(categories):
    first, _ = categories
    base = orm_registry.Registry('default')
    _assign(first)
    base.cache_invalidated.clear()
    _assign(first)
    assert base.cache_invalidated == set()


def test_reset_changes_drops_a_lookup_seeded_by_an_undone_move(categories):
    first, second = categories
    base = orm_registry.Registry('default')
    _assign(first)
    base.cache_invalidated.clear()
    with pytest.raises(RuntimeError):
        with _cursor() as cr, Environment(cr.alias, SUPERUSER_ID, {}):
            record = IrModuleCategory.objects.using(cr.alias).get(pk=second)
            IrModelData._update_xmlids(
                [{'xml_id': XMLID, 'record': record}], using=cr.alias)
            raise RuntimeError('deshacer')
    base.reset_changes()
    with Environment('default', SUPERUSER_ID, {}):
        assert IrModelData._xmlid_lookup(XMLID)[1] == first
