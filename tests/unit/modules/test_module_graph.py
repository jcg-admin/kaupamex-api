"""Contratos del grafo de módulos: orden válido y rechazo de ciclos."""
import pytest

from modules import module_graph


def graph_of(monkeypatch, dependencies):
    monkeypatch.setattr(module_graph, 'load_manifest',
                        lambda name: {'depends': dependencies.get(name, [])})
    graph = module_graph.ModuleGraph()
    graph.extend(list(dependencies))
    return graph


@pytest.mark.parametrize('dependencies,cycle', [
    ({'sale': ['delivery'], 'delivery': ['sale']}, ('sale', 'delivery', 'sale')),
    ({'base': ['base']}, ('base', 'base')),
    ({'a': ['b'], 'b': ['c'], 'c': ['b']}, ('b', 'c', 'b')),
])
def test_depth_rejects_cycle_with_a_domain_error(monkeypatch, dependencies, cycle):
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
    graph = graph_of(monkeypatch, {'sale': ['left', 'right'], 'right': ['base'],
                                 'left': ['base'], 'base': []})
    assert graph.order() == ['base', 'left', 'right', 'sale']
    assert graph['sale'].depth == 2


def test_depth_does_not_reuse_a_stale_memo_after_dependencies_change(monkeypatch):
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
    graph = graph_of(monkeypatch, {'sale': ['left', 'right'], 'right': ['base'],
                                 'left': ['base'], 'base': []})
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
