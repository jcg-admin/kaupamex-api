"""``modules.db.is_initialized`` e ``initialize``.

≙ ``odoo19c: odoo/modules/db.py:20-124``.

La fuente sólo inicializa una base sin módulos instalados
(``odoo/modules/loading.py:371-376``); la base de pruebas los tiene todos, así
que cada caso deja el catálogo sin instalar dentro de su transacción. Los
manifests son sintéticos, inyectados en ``update_module_list`` como en
``test_module_catalog_database.py``
(``designs/orm-modules-db-initialize-0058.md``).
"""
import pytest
from django.db import connection

from addons.base.management.commands import update_module_list as catalog
from addons.base.models import IrModelData, IrModule, IrModuleDependency
from exceptions import UserError
from modules import loading
from modules.db import initialize, is_initialized

pytestmark = pytest.mark.django_db


@pytest.fixture
def manifests(monkeypatch):
    values = {
        'init_root': {'name': 'Init Root', 'license': 'LGPL-3',
                      'depends': [], 'auto_install': []},
        'init_leaf': {'name': 'Init Leaf', 'license': 'LGPL-3',
                      'depends': ['init_root']},
        'init_bridge': {'name': 'Init Bridge', 'license': 'LGPL-3',
                        'depends': ['init_root', 'init_leaf'],
                        'auto_install': ['init_root']},
        'init_blocked': {'name': 'Init Blocked', 'license': 'LGPL-3',
                         'depends': ['init_root'], 'auto_install': True,
                         'installable': False},
    }
    monkeypatch.setattr(catalog, 'get_modules', lambda: list(values))
    monkeypatch.setattr(catalog, 'get_module_path', lambda name: name)
    monkeypatch.setattr(catalog, 'read_manifest', lambda name: values[name])
    monkeypatch.setattr(catalog.Command, '_report_auto_install_gaps',
                        lambda self, installed: None)
    return values


@pytest.fixture
def uninstalled():
    """El estado que la fuente ve al inicializar: nada instalado."""
    IrModule.objects.update(state=IrModule.STATE_UNINSTALLED)


def state(name):
    return IrModule.objects.get(name=name).state


def test_a_migrated_database_is_initialized():
    with connection.cursor() as cr:
        assert is_initialized(cr) is True


def test_a_schema_without_the_module_table_is_not():
    with connection.cursor() as cr:
        cr.execute('CREATE SCHEMA kaupamex_test_empty_schema')
        cr.execute('SET LOCAL search_path TO kaupamex_test_empty_schema')
        try:
            assert is_initialized(cr) is False
        finally:
            cr.execute('SET LOCAL search_path TO public')


def test_each_module_gets_its_base_identity_once(manifests, uninstalled):
    with connection.cursor() as cr:
        initialize(cr)
        initialize(cr)
    root = IrModule.objects.get(name='init_root')
    identities = IrModelData.objects.filter(module='base',
                                            name='module_init_root')
    assert identities.count() == 1
    identity = identities.get()
    assert (identity.res_id, identity.noupdate) == (root.pk, True)


def test_only_listed_dependencies_are_auto_install_required(
        manifests, uninstalled):
    with connection.cursor() as cr:
        initialize(cr)
    bridge = IrModule.objects.get(name='init_bridge')
    required = dict(IrModuleDependency.objects.filter(
        module_id=bridge.pk).values_list('name', 'auto_install_required'))
    assert required == {'init_root': True, 'init_leaf': False}


def test_auto_install_marks_the_closure_but_never_an_uninstallable(
        manifests, uninstalled):
    with connection.cursor() as cr:
        initialize(cr)
    assert state('init_root') == IrModule.STATE_TO_INSTALL
    # El puente entra por su dependencia requerida; la no requerida se
    # arrastra con él (``db.py:111-120``).
    assert state('init_bridge') == IrModule.STATE_TO_INSTALL
    assert state('init_leaf') == IrModule.STATE_TO_INSTALL
    assert state('init_blocked') == IrModule.STATE_UNINSTALLABLE


def test_skipping_auto_install_marks_only_base(manifests, uninstalled):
    with connection.cursor() as cr:
        initialize(cr, skip_auto_install=True)
    assert state('base') == IrModule.STATE_TO_INSTALL
    assert state('init_root') == IrModule.STATE_UNINSTALLED


def test_an_installed_module_refuses_and_changes_nothing(manifests,
                                                         uninstalled):
    IrModule.objects.filter(name='base').update(
        state=IrModule.STATE_INSTALLED)
    before = dict(IrModule.objects.values_list('name', 'state'))
    with connection.cursor() as cr, pytest.raises(UserError,
                                                  match='installed'):
        initialize(cr)
    assert dict(IrModule.objects.values_list('name', 'state')) == before


def test_loading_an_uninitialized_database_stops_before_the_catalog(
        monkeypatch):
    """≙ ``odoo19c: odoo/modules/loading.py:371-373``."""
    calls = []
    monkeypatch.setattr(loading, 'is_initialized', lambda cr: False)
    monkeypatch.setattr(loading, 'call_command',
                        lambda *args, **kwargs: calls.append(args))
    assert loading.load_modules('default') is None
    assert calls == []
