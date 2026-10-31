"""El arranque respeta installable antes de importar modelos de addons."""
import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings import base
from modules import module_graph


def local_apps(monkeypatch, manifests):
    """Conserva el grafo real y controla sólo los manifests descubiertos."""
    monkeypatch.setattr(base, 'get_modules', lambda: list(manifests))
    monkeypatch.setattr(module_graph, 'load_manifest', manifests.__getitem__)
    return base._local_apps()


def test_noninstallable_addon_is_not_a_django_app(monkeypatch):
    assert local_apps(monkeypatch, {
        'base': {'depends': []},
        'disabled': {'depends': ['base'], 'installable': False},
        'enabled': {'depends': ['base'], 'installable': True},
    }) == ('core', 'addons.base', 'addons.enabled')


def test_dependents_of_disabled_addon_are_pruned_before_loading(monkeypatch):
    assert local_apps(monkeypatch, {
        'base': {'depends': []},
        'disabled': {'depends': ['base'], 'installable': False},
        'child': {'depends': ['disabled']},
        'grandchild': {'depends': ['child']},
    }) == ('core', 'addons.base')


def test_cycle_in_disabled_component_does_not_block_retained_apps(monkeypatch):
    assert local_apps(monkeypatch, {
        'base': {'depends': []},
        'disabled': {'depends': ['cycle'], 'installable': False},
        'cycle': {'depends': ['disabled']},
    }) == ('core', 'addons.base')


def test_cycle_in_enabled_component_still_rejects_startup(monkeypatch):
    with pytest.raises(ImproperlyConfigured, match='ciclo'):
        local_apps(monkeypatch, {
            'base': {'depends': []}, 'first': {'depends': ['second']},
            'second': {'depends': ['first']},
        })


def test_missing_flag_keeps_legacy_default_and_dependency_order(monkeypatch):
    assert local_apps(monkeypatch, {
        'leaf': {'depends': ['middle']}, 'base': {'depends': []},
        'middle': {'depends': ['base']},
    }) == ('core', 'addons.base', 'addons.middle', 'addons.leaf')
