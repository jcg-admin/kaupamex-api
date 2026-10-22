"""Snapshot de carga por base; no ejecuta solicitudes ni instala addons."""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils.connection import ConnectionDoesNotExist

from addons.base.models.ir_module import IrModule
from modules import module_graph
from modules.module_graph import ModuleGraph

pytestmark = pytest.mark.django_db


@pytest.fixture
def graph_manifests(monkeypatch):
    manifests = {
        'base': {'depends': [], 'installable': True},
        'snapshot_child': {'depends': ['base'], 'installable': True},
        'snapshot_independent': {'depends': [], 'installable': True},
    }
    monkeypatch.setattr(module_graph, 'load_manifest', manifests.__getitem__)
    return manifests


def seed(state='installed'):
    IrModule.objects.bulk_create([
        IrModule(name='base', state=state, version='manifest-new',
                 installed_version='installed-old', demo=True),
        IrModule(name='snapshot_child', state='installed'),
        IrModule(name='snapshot_independent', state='installed'),
    ])


def test_snapshot_copies_persisted_identity_state_demo_and_installed_version(graph_manifests):
    seed('to upgrade')
    row = IrModule.objects.get(name='base')
    with CaptureQueriesContext(connection) as queries:
        graph = ModuleGraph.from_database(['snapshot_child'], using='default')
    assert len(queries) == 1
    node = graph['base']
    assert (node.id, node.state, node.demo) == (row.pk, 'to upgrade', True)
    assert node.installed_version == node.load_version == 'installed-old'
    assert node.load_state == 'to upgrade'
    assert IrModule.objects.get(pk=row.pk).version == 'manifest-new'
    assert [node.name for node in graph] == ['base', 'snapshot_child']


@pytest.mark.parametrize('mode', ['load', 'update'])
@pytest.mark.parametrize('state', [
    'installed', 'to upgrade', 'to remove', 'to install', 'uninstalled', 'uninstallable',
])
def test_snapshot_mode_filters_and_prunes_dependents(graph_manifests, mode, state):
    seed(state)
    graph = ModuleGraph.from_database(
        ['snapshot_child', 'snapshot_independent'], using='default', mode=mode)
    retained = state != 'uninstallable' and not (
        mode == 'load' and state in ('uninstalled', 'to install'))
    assert ('base' in graph) is retained
    assert ('snapshot_child' in graph) is retained
    assert 'snapshot_independent' in graph
    assert IrModule.objects.get(name='base').state == state


def test_snapshot_does_not_invent_unknown_installed_versions(graph_manifests):
    seed()
    graph = ModuleGraph.from_database(['snapshot_child'], using='default')
    assert graph['snapshot_child'].installed_version is None
    assert graph['snapshot_child'].load_version is None


def test_empty_snapshot_does_not_query(graph_manifests):
    with CaptureQueriesContext(connection) as queries:
        graph = ModuleGraph.from_database([], using='default')
    assert len(graph) == 0
    assert len(queries) == 0


def test_snapshot_rejects_unknown_database(graph_manifests):
    with pytest.raises(ConnectionDoesNotExist):
        ModuleGraph.from_database(['base'], using='not_registered')


@pytest.mark.parametrize('problem', ['cycle', 'uninstallable_manifest', 'missing_manifest'])
def test_snapshot_preparation_prunes_unloadable_code(graph_manifests, problem):
    seed()
    if problem == 'cycle':
        graph_manifests['base']['depends'] = ['snapshot_child']
    elif problem == 'uninstallable_manifest':
        graph_manifests['base']['installable'] = False
    else:
        graph_manifests['base'] = {}
    graph = ModuleGraph.from_database(
        ['snapshot_child', 'snapshot_independent'], using='default')
    assert 'base' not in graph
    assert 'snapshot_child' not in graph
    assert 'snapshot_independent' in graph
    assert IrModule.objects.get(name='base').state == 'installed'


def test_snapshot_does_not_remove_an_already_pruned_row_twice(graph_manifests):
    seed('uninstallable')
    IrModule.objects.filter(name='snapshot_child').update(state='uninstallable')
    graph = ModuleGraph.from_database(
        ['snapshot_child', 'snapshot_independent'], using='default')
    assert 'base' not in graph
    assert 'snapshot_child' not in graph
    assert 'snapshot_independent' in graph
