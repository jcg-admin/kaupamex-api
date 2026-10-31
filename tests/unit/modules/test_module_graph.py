"""Contratos del grafo de módulos: orden válido y rechazo de ciclos."""

import logging
from unittest.mock import Mock

import pytest

from modules import module_graph


def graph_of(monkeypatch, dependencies):
    monkeypatch.setattr(module_graph, 'load_manifest',
                        lambda name: {'depends': dependencies.get(name, [])})
    graph = module_graph.ModuleGraph()
    graph.extend(list(dependencies))
    return graph


@pytest.mark.parametrize(
    'dependencies,cycle',
    [
        (
            {'sale': ['delivery'], 'delivery': ['sale']},
            ('sale', 'delivery', 'sale'),
        ),
        ({'base': ['base']}, ('base', 'base')),
        ({'a': ['b'], 'b': ['c'], 'c': ['b']}, ('b', 'c', 'b')),
    ],
)
def test_depth_rejects_cycle_with_a_domain_error(
    monkeypatch, dependencies, cycle
):
    graph = graph_of(monkeypatch, dependencies)
    with pytest.raises(ValueError, match=' -> '.join(cycle)) as error:
        _ = graph[next(iter(dependencies))].depth
    assert type(error.value).__name__ == 'ModuleGraphCycle'
    assert error.value.cycle == cycle


def test_order_rejects_cycles_before_returning_a_partial_plan(monkeypatch):
    graph = graph_of(monkeypatch, {'base': [], 'a': ['b'], 'b': ['a']})
    with pytest.raises(ValueError, match='a -> b -> a'):
        graph.order()


def test_diamond_is_not_a_cycle_and_ties_are_deterministic(monkeypatch):
    graph = graph_of(
        monkeypatch,
        {
            'sale': ['left', 'right'],
            'right': ['base'],
            'left': ['base'],
            'base': [],
        },
    )
    assert graph.order() == ['base', 'left', 'right', 'sale']
    assert graph['sale'].depth == 2


def test_depth_does_not_reuse_a_stale_memo_after_dependencies_change(
    monkeypatch,
):
    graph = graph_of(monkeypatch, {'a': ['b'], 'b': []})
    assert graph['a'].depth == 1
    graph['b'].depends.append('a')
    with pytest.raises(ValueError, match='a -> b -> a'):
        _ = graph['a'].depth


def test_missing_dependency_is_reported_without_inventing_a_cycle(monkeypatch):
    graph = graph_of(monkeypatch, {'sale': ['absent']})
    monkeypatch.setattr(module_graph, 'get_module_path',
                        lambda name: None if name == 'absent' else '/fixture')
    assert graph.missing() == {'sale': ['absent']}
    assert graph.cycles() == []


def test_each_node_depth_is_computed_once_per_ordering(monkeypatch):
    graph = graph_of(
        monkeypatch,
        {
            'sale': ['left', 'right'],
            'right': ['base'],
            'left': ['base'],
            'base': [],
        },
    )
    visits = {}

    class Dependencies(list):
        def __iter__(self):
            visits[id(self)] = visits.get(id(self), 0) + 1
            return super().__iter__()

    for name, node in graph._nodes.items():
        node.depends = Dependencies(node.depends)
    assert graph.order() == ['base', 'left', 'right', 'sale']
    assert len(visits) == 4
    assert set(visits.values()) == {1}


@pytest.mark.parametrize('trigger', [[], ()])
def test_empty_auto_install_trigger_is_not_false(monkeypatch, trigger):
    graph = graph_of(monkeypatch, {'base': [], 'bridge': ['base']})
    graph['bridge'].manifest['auto_install'] = trigger
    assert graph.auto_installable([]) == ['bridge']


def test_uninstallable_module_is_not_an_auto_install_candidate(monkeypatch):
    graph = graph_of(monkeypatch, {'disabled': []})
    graph['disabled'].manifest.update(auto_install=True, installable=False)
    assert graph.auto_installable([]) == []


def test_true_trigger_requires_dependencies_and_false_never_qualifies(
    monkeypatch,
):
    graph = graph_of(
        monkeypatch, {'base': [], 'bridge': ['base'], 'manual': []}
    )
    graph['bridge'].manifest['auto_install'] = True
    graph['manual'].manifest['auto_install'] = False
    assert graph.auto_installable([]) == []
    assert graph.auto_installable(['base']) == ['bridge']


@pytest.fixture
def bound_graph(monkeypatch):
    """Aísla el catálogo para verificar la orquestación incremental."""
    manifests = {
        'base': {'depends': [], 'installable': True},
        'child': {'depends': ['base'], 'installable': True},
        'disabled': {'depends': ['base'], 'installable': False},
        'cycle_a': {'depends': ['cycle_b'], 'installable': True},
        'cycle_b': {'depends': ['cycle_a'], 'installable': True},
    }
    monkeypatch.setattr(module_graph, 'load_manifest', manifests.__getitem__)
    calls = []

    def snapshot(graph, names, *, using):
        assert using == 'default'
        names = tuple(name for name in names if name in graph)
        calls.append(names)
        for name in names:
            node = graph[name]
            node.id = 11 if name == 'base' else 22
            node.state = node.load_state = (
                'installed' if name == 'base' else 'to install'
            )
            node.installed_version = node.load_version = 'persisted-old'
            node.demo = True

    monkeypatch.setattr(
        module_graph.ModuleGraph, '_update_from_database', snapshot
    )
    graph = module_graph.ModuleGraph.from_database(
        ['base'], using='default', mode='update'
    )
    return graph, calls


def test_bound_extension_snapshots_new_nodes_without_overwriting_loaded_state(
    bound_graph,
):
    graph, calls = bound_graph
    graph['base'].state = 'to upgrade'
    graph.extend(['child'])
    child = graph['child']
    assert (child.id, child.state, child.load_state, child.demo) == (
        22,
        'to install',
        'to install',
        True,
    )
    assert child.installed_version == child.load_version == 'persisted-old'
    assert child.phase == 2
    assert graph['base'].state == 'to upgrade'
    assert graph['base'].load_state == 'installed'
    assert calls == [('base',), ('child',)]


def test_bound_extension_prunes_uninstallable_manifests(bound_graph):
    graph, _ = bound_graph
    graph.extend(['disabled'])
    assert set(graph._nodes) == {'base'}


def test_bound_extension_prunes_new_dependency_cycles(bound_graph):
    graph, _ = bound_graph
    graph.extend(['cycle_a'])
    assert set(graph._nodes) == {'base'}


def test_bound_extension_of_existing_nodes_does_not_reload_catalogue(
    bound_graph,
):
    graph, calls = bound_graph
    graph.extend(['base'])
    assert calls == [('base',)]


def test_bound_extension_reports_the_uninstallable_root(bound_graph, caplog):
    """El descarte debe identificar al módulo raíz, no sólo dependientes."""
    graph, _ = bound_graph
    with caplog.at_level(logging.WARNING, logger='modules.module_graph'):
        graph.extend(['disabled'])
    assert set(graph._nodes) == {'base'}
    messages = [
        (record.levelno, record.getMessage()) for record in caplog.records
    ]
    assert messages == [
        (logging.WARNING, 'module disabled: not installable, skipped'),
    ]


@pytest.mark.parametrize(
    'state,level,message',
    [
        ('uninstallable', logging.WARNING, 'not installable'),
        ('uninstalled', logging.INFO, 'not installed'),
        ('to install', logging.INFO, 'not installed'),
    ],
)
def test_catalogue_pruning_reports_the_reason_and_keeps_dependency_logs(
    monkeypatch, caplog, state, level, message,
):
    """El catálogo seleccionado explica la poda sin escribir estados."""
    graph = graph_of(monkeypatch, {'root': [], 'child': ['root']})
    model = Mock()
    queryset = model.objects.using.return_value.filter.return_value
    ordered = queryset.order_by.return_value
    ordered.values_list.return_value = [
        ('root', 1, state, False, None),
        ('child', 2, 'installed', False, '1.0'),
    ]
    monkeypatch.setattr(module_graph.apps, 'get_model', lambda *args: model)
    with caplog.at_level(logging.INFO, logger='modules.module_graph'):
        graph._update_from_database(['root', 'child'], using='catalogue')
    assert not graph._nodes
    messages = [
        (record.levelno, record.getMessage()) for record in caplog.records
    ]
    assert messages == [
        (level, f'module root: {message}, skipped'),
        (
            logging.INFO,
            'module child: its direct/indirect dependency is skipped, skipped',
        ),
    ]
    model.objects.using.assert_called_once_with('catalogue')
    assert not model.objects.create.called
    assert not queryset.update.called


@pytest.mark.parametrize('state', ['uninstalled', 'to install'])
def test_update_snapshot_does_not_report_a_valid_install_request_as_skipped(
    monkeypatch, caplog, state,
):
    """El modo update conserva la solicitud y no emite un falso descarte."""
    graph = graph_of(monkeypatch, {'root': []})
    graph.mode = 'update'
    model = Mock()
    queryset = model.objects.using.return_value.filter.return_value
    queryset.order_by.return_value.values_list.return_value = [
        ('root', 1, state, False, None),
    ]
    monkeypatch.setattr(module_graph.apps, 'get_model', lambda *args: model)
    with caplog.at_level(logging.INFO, logger='modules.module_graph'):
        graph._update_from_database(['root'], using='catalogue')
    assert graph['root'].state == state
    assert graph['root'].load_state == state
    assert caplog.records == []
