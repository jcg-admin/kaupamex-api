"""Transiciones programadas son atómicas y distintas de instalar un módulo."""
import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from addons.base.models.ir_module import IrModule, IrModuleDependency
from modules import module_graph
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def module_rows(monkeypatch):
    manifests = {
        'state_root': {'depends': [], 'installable': True},
        'state_leaf': {'depends': ['state_root'], 'installable': True},
        'state_bridge': {'depends': ['state_leaf'], 'auto_install': True},
    }
    monkeypatch.setattr(module_graph, 'load_manifest', lambda name: manifests.get(name, {}))
    IrModule.objects.bulk_create([IrModule(name=name) for name in manifests])
    IrModuleDependency.objects.bulk_create([
        IrModuleDependency(module=IrModule.objects.get(name=name), name=dep)
        for name, manifest in manifests.items() for dep in manifest.get('depends', [])
    ])
    return manifests


def row(name='state_leaf'):
    return IrModule.objects.get(name=name)


def states():
    return dict(IrModule.objects.filter(name__startswith='state_').values_list('name', 'state'))


def test_install_schedules_dependency_order_and_auto_install(module_rows):
    with sudo():
        assert row().button_install() == ['state_root', 'state_leaf', 'state_bridge']
    assert set(states().values()) == {'to install'}
    assert not IrModule.objects.filter(name__startswith='state_', state='installed').exists()


def test_missing_dependency_never_partially_schedules(module_rows):
    module_rows['state_leaf']['depends'].append('missing_module')
    with sudo(), pytest.raises(ValidationError, match='Missing module dependency'):
        row().button_install()
    assert set(states().values()) == {'uninstalled'}


def test_cycle_never_partially_schedules(module_rows):
    module_rows['state_root']['depends'] = ['state_leaf']
    with sudo(), pytest.raises(ValueError, match='ModuleGraphCycle'):
        row().button_install()
    assert set(states().values()) == {'uninstalled'}


def test_disabled_dependency_is_rejected(module_rows):
    module_rows['state_root']['installable'] = False
    with sudo(), pytest.raises(ValidationError, match='not installable'):
        row().button_install()
    assert set(states().values()) == {'uninstalled'}


def test_external_dependency_is_checked_before_writes(module_rows):
    module_rows['state_leaf']['external_dependencies'] = {'bin': ['missing_kaupamex_fixture_binary']}
    with sudo(), pytest.raises(ValidationError, match='Missing executable dependency'):
        row().button_install()
    assert set(states().values()) == {'uninstalled'}


def test_request_requires_system_actor(module_rows):
    with pytest.raises(PermissionDenied):
        row().button_install()
    assert set(states().values()) == {'uninstalled'}


def test_upgrade_schedules_installed_dependents(module_rows):
    IrModule.objects.filter(name__startswith='state_').update(state='installed')
    with sudo():
        row('state_root').button_upgrade()
    assert set(states().values()) == {'to upgrade'}


def test_uninstall_schedules_installed_dependents_without_deleting(module_rows):
    IrModule.objects.filter(name__startswith='state_').update(state='installed')
    with sudo():
        assert row('state_root').button_uninstall() == ['state_bridge', 'state_leaf', 'state_root']
    assert set(states().values()) == {'to remove'}
    assert IrModuleDependency.objects.filter(module__name__startswith='state_').count() == 2


def test_upgrade_rejects_uninstalled_module(module_rows):
    with sudo(), pytest.raises(ValidationError, match='not installed'):
        row().button_upgrade()
    assert set(states().values()) == {'uninstalled'}
