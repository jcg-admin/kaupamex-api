"""Las cachés de ``ormcache`` y su registro de invalidación son del
``Registry`` de cada base.

≙ ``Registry.__init__`` (``odoo19c: odoo/orm/registry.py:233,282``): cada
registro crea ``self.__caches`` y ``self._invalidation_flags``, y
``ormcache.lookup`` lee ``model.pool._Registry__caches``
(``odoo/tools/cache.py:127``). La clave ``(self._name, method, *args)`` no
lleva la base porque el contenedor ya es de ella. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
registry-caches-per-database.md``.

Las dos bases son dos alias sobre la misma base de pruebas, cada uno en su
transacción que se revierte; la del alias de sondeo renombra la fila de
``ir.model`` que la otra no ve.
"""
import pytest
from django.conf import settings
from django.db import connections, transaction

from addons.base.models import IrModel, IrModelData
from addons.base.models.ir_module import IrModuleCategory
from orm import registry as orm_registry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

PROBE_ALIAS = 'registry_caches_probe'


@pytest.fixture
def probe_alias(django_db_setup, django_db_blocker):
    assert PROBE_ALIAS not in settings.DATABASES
    settings.DATABASES[PROBE_ALIAS] = dict(
        connections['default'].settings_dict)
    try:
        with django_db_blocker.unblock(), \
                transaction.atomic(using='default'), \
                transaction.atomic(using=PROBE_ALIAS):
            yield PROBE_ALIAS
            transaction.set_rollback(True, using=PROBE_ALIAS)
            transaction.set_rollback(True, using='default')
    finally:
        orm_registry.Registry.registries.pop(PROBE_ALIAS, None)
        connections[PROBE_ALIAS].close()
        del connections[PROBE_ALIAS]
        del settings.DATABASES[PROBE_ALIAS]


def _hide_model(alias, name):
    with connections[alias].cursor() as cr:
        cr.execute("UPDATE ir_model SET model = 'probe.hidden' "
                   "WHERE model = %s", [name])


def test_an_entry_of_one_database_is_not_served_to_another(probe_alias):
    name = IrModel.objects.using('default').order_by('pk').values_list(
        'model', flat=True).first()
    assert name
    with Environment('default', SUPERUSER_ID, {}):
        assert IrModel._get_id(name) is not None
    _hide_model(probe_alias, name)
    with Environment(probe_alias, SUPERUSER_ID, {}):
        assert IrModel._get_id(name) is None


def test_clearing_one_registry_leaves_the_other_alone(probe_alias):
    default = orm_registry.Registry('default')
    probe = orm_registry.Registry(probe_alias)
    default.cache_invalidated.clear()
    probe.cache_invalidated.clear()
    with Environment('default', SUPERUSER_ID, {}):
        IrModel._get_id(IrModel.objects.using('default').values_list(
            'model', flat=True).first())
    assert len(default._caches['stable'])
    probe.clear_cache('stable')
    assert len(default._caches['stable'])
    assert probe.cache_invalidated == {'stable'}
    assert 'stable' not in default.cache_invalidated


def test_module_clear_cache_goes_to_the_active_registry(probe_alias):
    default = orm_registry.Registry('default')
    probe = orm_registry.Registry(probe_alias)
    default.cache_invalidated.clear()
    probe.cache_invalidated.clear()
    with Environment(probe_alias, SUPERUSER_ID, {}):
        orm_registry.clear_cache('groups')
    assert probe.cache_invalidated == {'groups'}
    assert default.cache_invalidated == set()


@pytest.mark.django_db
def test_a_failed_load_resets_the_registry_changes(monkeypatch):
    """≙ ``models.py:1061-1063``: *"cancel all changes done to the
    registry/ormcache"* cuando la importación se deshace."""
    calls = []
    monkeypatch.setattr(orm_registry.Registry, 'reset_changes',
                        lambda self: calls.append(self))
    result = IrModuleCategory.load(
        ['name', 'sequence'], [['Probe', 'no-soy-un-entero']])
    assert result['ids'] is False
    assert calls == [orm_registry.Registry('default')]


def _first_xmlid(alias):
    row = IrModelData.objects.using(alias).order_by('pk').values_list(
        'module', 'name').first()
    return '%s.%s' % row


def test_a_bulk_delete_of_an_xmlid_invalidates_its_database(probe_alias):
    """≙ ``unlink`` (``odoo19c: ir_model.py:2328-2334``): todo borrado vacía
    la caché. ``QuerySet.delete`` no llama a ``Model.delete``; el vaciado
    tiene que llegar igual, y al registro de la base de la fila."""
    xmlid = _first_xmlid(probe_alias)
    module, name = xmlid.split('.', 1)
    with Environment(probe_alias, SUPERUSER_ID, {}):
        assert IrModelData._xmlid_lookup(xmlid, using=probe_alias)
    with Environment('default', SUPERUSER_ID, {}):
        IrModelData.objects.using(probe_alias).filter(
            module=module, name=name).delete()
    with pytest.raises(ValueError):
        IrModelData._xmlid_lookup(xmlid, using=probe_alias)


def test_saving_an_xmlid_row_invalidates_its_database(probe_alias):
    xmlid = _first_xmlid(probe_alias)
    module, name = xmlid.split('.', 1)
    with Environment(probe_alias, SUPERUSER_ID, {}):
        model, res_id = IrModelData._xmlid_lookup(xmlid, using=probe_alias)
    row = IrModelData.objects.using(probe_alias).get(module=module, name=name)
    row.res_id = res_id + 1000000
    with Environment('default', SUPERUSER_ID, {}):
        row.save(using=probe_alias)
    assert IrModelData._xmlid_lookup(xmlid, using=probe_alias)[1] == (
        res_id + 1000000)
