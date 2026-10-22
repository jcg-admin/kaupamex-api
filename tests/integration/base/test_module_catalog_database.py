"""El catálogo no instala código ni reemplaza el estado persistido de una base."""
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from addons.base.models import IrModule, IrModuleDependency
from addons.base.management.commands import update_module_list as catalog

pytestmark = pytest.mark.django_db


@pytest.fixture
def manifests(monkeypatch):
    values = {
        'catalog_root': {'name': 'Catalog Root', 'license': 'LGPL-3',
                         'depends': [], 'installable': True},
        'catalog_leaf': {'name': 'Catalog Leaf', 'license': 'LGPL-3',
                         'depends': ['catalog_root'], 'installable': True},
    }
    monkeypatch.setattr(catalog, 'get_modules', lambda: list(values))
    monkeypatch.setattr(catalog, 'get_module_path', lambda name: name)
    monkeypatch.setattr(catalog, 'read_manifest', lambda name: values[name])
    monkeypatch.setattr(catalog.Command, '_report_auto_install_gaps',
                        lambda self, installed: None)
    return values


def refresh(**options):
    call_command('update_module_list', stdout=io.StringIO(), **options)


def test_refresh_does_not_install_importable_code(manifests, monkeypatch):
    monkeypatch.setattr(catalog, 'installed_addon_names', lambda: set(manifests))
    refresh()
    assert set(IrModule.objects.filter(name__in=manifests).values_list(
        'state', flat=True)) == {IrModule.STATE_UNINSTALLED}


def test_refresh_preserves_existing_state_and_updates_metadata(manifests):
    IrModule.objects.bulk_create([
        IrModule(name='catalog_root', state=IrModule.STATE_INSTALLED),
        IrModule(name='catalog_leaf', state=IrModule.STATE_UNINSTALLED),
    ])
    refresh()
    assert IrModule.objects.get(name='catalog_root').state == IrModule.STATE_INSTALLED
    assert IrModule.objects.get(name='catalog_leaf').state == IrModule.STATE_UNINSTALLED
    assert IrModule.objects.get(name='catalog_leaf').shortdesc == 'Catalog Leaf'
    assert list(IrModuleDependency.objects.filter(
        module__name='catalog_leaf').values_list('name', flat=True)) == ['catalog_root']


def test_manifest_change_cannot_silently_uninstall_an_installed_module(manifests):
    IrModule.objects.bulk_create([
        IrModule(name='catalog_leaf', state=IrModule.STATE_INSTALLED),
    ])
    manifests['catalog_leaf']['installable'] = False
    refresh()
    assert IrModule.objects.get(name='catalog_leaf').state == IrModule.STATE_INSTALLED


def test_catalog_refresh_is_atomic_on_dependency_failure(manifests, monkeypatch):
    original = catalog.Command._sync_dependencies

    def fail(self, module, depends, **kwargs):
        if module.name == 'catalog_leaf':
            raise RuntimeError('dependency write failed')
        return original(self, module, depends, **kwargs)

    monkeypatch.setattr(catalog.Command, '_sync_dependencies', fail)
    with pytest.raises(RuntimeError, match='dependency write failed'):
        refresh()
    assert not IrModule.objects.filter(name__in=manifests).exists()


def test_unknown_database_is_rejected_before_catalog_writes(manifests):
    with pytest.raises(CommandError, match='database'):
        refresh(database='not_registered')
    assert not IrModule.objects.filter(name__in=manifests).exists()


def test_dry_run_does_not_change_states_or_dependencies(manifests):
    IrModule.objects.bulk_create([
        IrModule(name='catalog_root', state=IrModule.STATE_INSTALLED),
    ])
    refresh(dry_run=True)
    assert IrModule.objects.filter(name__in=manifests).count() == 1
    assert IrModule.objects.get(name='catalog_root').state == IrModule.STATE_INSTALLED
    assert not IrModuleDependency.objects.filter(module__name__in=manifests).exists()


@pytest.mark.parametrize('previous,installable,expected', [
    ('uninstallable', True, 'uninstalled'),
    ('uninstalled', False, 'uninstallable'),
])
def test_availability_refresh_only_changes_non_operational_states(
        manifests, previous, installable, expected):
    IrModule.objects.bulk_create([IrModule(name='catalog_leaf', state=previous)])
    manifests['catalog_leaf']['installable'] = installable
    refresh()
    assert IrModule.objects.get(name='catalog_leaf').state == expected
