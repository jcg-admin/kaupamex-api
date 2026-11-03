"""Depth diagnostics must not depend on the interpreter recursion limit."""

import sys

import pytest

from modules import module_graph


def graph_of(monkeypatch, dependencies):
    monkeypatch.setattr(
        module_graph, 'load_manifest',
        lambda name: {'depends': dependencies.get(name, [])},
    )
    graph = module_graph.ModuleGraph()
    graph.extend(list(dependencies))
    return graph


def long_path():
    names = [f'node_{i:05d}' for i in range(sys.getrecursionlimit() + 20)]
    dependencies = {
        name: names[index + 1:index + 2]
        for index, name in enumerate(names)
    }
    return names, dependencies


def test_deep_cycle_reports_its_route_instead_of_recursion_error(monkeypatch):
    names, dependencies = long_path()
    dependencies[names[-1]] = [names[0]]
    graph = graph_of(monkeypatch, dependencies)

    with pytest.raises(module_graph.ModuleGraphCycle) as error:
        _ = graph[names[0]].depth

    assert error.value.cycle == (*names, names[0])


def test_deep_acyclic_path_has_unchanged_depth_and_order(monkeypatch):
    names, dependencies = long_path()
    graph = graph_of(monkeypatch, dependencies)

    assert graph[names[0]].depth == len(names) - 1
    assert graph.order() == list(reversed(names))


def test_cycle_failure_preserves_the_callers_path(monkeypatch):
    graph = graph_of(monkeypatch, {'a': ['b'], 'b': ['a']})
    path = {'caller': 0}

    with pytest.raises(module_graph.ModuleGraphCycle) as error:
        graph._depth(graph['a'], {}, path)

    assert error.value.cycle == ('a', 'b', 'a')
    assert path == {'caller': 0}
