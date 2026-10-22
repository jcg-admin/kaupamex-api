"""Bounded differential verification, not native Odoo loader acceptance."""
import __future__
import ast
import functools
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'src'))

from counterpart_body import declarations_of  # noqa: E402
from reference_roots import tree  # noqa: E402
from modules.module_graph import ModuleGraph  # noqa: E402


@pytest.fixture
def reference_node():
    source = tree('odoo19c') / 'odoo/modules/module_graph.py'
    declaration = next(d for d in declarations_of(source)
                       if d.kind == 'class' and d.name == 'ModuleNode')
    namespace = {'functools': functools}
    # Execute the unmodified reference class only. Constructors, cursor,
    # manifests and native Odoo infrastructure are deliberately not executed.
    code = compile(ast.Module(body=[declaration.node], type_ignores=[]),
                   str(source), 'exec', flags=__future__.annotations.compiler_flag)
    exec(code, namespace)
    return namespace['ModuleNode']


@pytest.fixture
def reference_graph():
    source = tree('odoo19c') / 'odoo/modules/module_graph.py'
    declaration = next(d for d in declarations_of(source)
                       if d.kind == 'class' and d.name == 'ModuleGraph')
    namespace = {'functools': functools, 'OrderedSet': set,
                 '_logger': logging.getLogger('pinned_module_graph')}
    code = compile(ast.Module(body=[declaration.node], type_ignores=[]),
                   str(source), 'exec', flags=__future__.annotations.compiler_flag)
    exec(code, namespace)
    return namespace['ModuleGraph']


def graphs(reference_node, manifests):
    reference = {}
    for name in manifests:
        node = object.__new__(reference_node)
        node.name = name
        node.manifest = manifests[name]
        node.demo = False
        node.state = 'installed'
        node.module_graph = SimpleNamespace(mode='load')
        reference[name] = node
    for name, manifest in manifests.items():
        reference[name].depends = [reference[d] for d in manifest['depends']]
    with patch('modules.module_graph.load_manifest', side_effect=manifests.__getitem__):
        consumer = ModuleGraph()
        consumer.extend(list(manifests))
    return reference, consumer


def test_ordinary_depth_and_order_key_agree(reference_node):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
                                      'sale': {'depends': ['base']}})
    assert [ref[n].depth for n in ('base', 'sale')] == [0, 1]
    assert [ours[n].depth for n in ('base', 'sale')] == [0, 1]
    assert ref['sale'].order_name == 'sale'
    assert ours['sale'].order_name == ref['sale'].order_name


def test_test_addon_placement_matches_reference(reference_node):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
        'aaa': {'depends': ['base']}, 'test_base': {'depends': ['base']}})
    assert ref['test_base'].depth == 0
    assert ours['test_base'].depth == ref['test_base'].depth
    assert ref['test_base'].order_name == 'base test_base'
    assert [n.name for n in sorted(ref.values(), key=lambda n: (n.depth, n.order_name))] == ['base', 'test_base', 'aaa']
    assert ours.order() == ['base', 'test_base', 'aaa']


def test_reference_phase_depends_on_mode_and_pending_state(reference_node):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
        'sale': {'depends': ['base']}, 'bridge': {'depends': ['sale']}})
    assert ref['base'].phase == 0
    assert ref['sale'].phase == ref['bridge'].phase == 1
    assert ours['base'].phase == 0
    assert ours['sale'].phase == ours['bridge'].phase == 1
    for node in ref.values():
        node.__dict__.pop('phase', None)
        node.module_graph.mode = 'update'
    ref['sale'].state = 'to install'
    ours.mode = 'update'
    ours['sale'].state = 'to install'
    assert ref['sale'].phase == 2
    assert ref['bridge'].phase == 3
    assert ours['sale'].phase == ref['sale'].phase
    assert ours['bridge'].phase == ref['bridge'].phase


@pytest.mark.parametrize('state', ['installed', 'to install', 'to upgrade', 'to remove'])
def test_phase_and_iteration_match_reference_for_state_boundaries(reference_node, state):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
        'a': {'depends': ['base']}, 'zz': {'depends': ['a']},
        'new': {'depends': ['base']}, 'child': {'depends': ['new']}})
    ours.mode = 'update'
    for node in ref.values():
        node.module_graph.mode = 'update'
    ref['new'].state = ours['new'].state = state
    for name in ref:
        ours[name].state = ref[name].state
    assert {name: ours[name].phase for name in ref} == {name: ref[name].phase for name in ref}
    assert ours.order() == [n.name for n in sorted(ref.values(), key=lambda n: (n.phase, n.depth, n.order_name))]
    # State mutation must not leave a stale phase in the Consumer.
    ours['new'].state = 'installed'
    assert ours['new'].phase == 1
    assert ours['child'].phase == 1


def test_demo_eligibility_is_dependency_based(reference_node):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
                                      'sale': {'depends': ['base']}})
    assert ref['base'].demo_installable is True
    assert ref['sale'].demo_installable is False
    assert ours['base'].demo_installable is True
    assert ours['sale'].demo_installable is False
    ref['base'].demo = True
    ours['base'].demo = True
    assert ref['sale'].demo_installable is True
    assert ours['sale'].demo_installable is True
    ours['base'].demo = False
    assert ours['sale'].demo_installable is False


def test_static_graph_membership_lookup_and_cardinality(reference_node, reference_graph):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
                                      'sale': {'depends': ['base']}})
    native = reference_graph(None)
    assert len(native) == len(ModuleGraph()) == 0
    native._modules = ref
    assert len(ours) == len(native) == 2
    assert ('sale' in ours) == ('sale' in native) is True
    assert ('absent' in ours) == ('absent' in native) is False
    assert ours['sale'].name == native['sale'].name
    for graph in (ours, native):
        with pytest.raises(KeyError):
            graph['absent']


@pytest.mark.parametrize('manifests', [
    {'base': {'depends': []}, 'a': {'depends': ['base']},
     'z': {'depends': ['base']}, 'test_tie': {'depends': ['a', 'z']}},
    {'base': {'depends': []}, 'test_base': {'depends': ['base']},
     'test_nested': {'depends': ['test_base']}, 'a': {'depends': ['base']}},
])
def test_test_addon_ties_and_nested_anchors(reference_node, manifests):
    ref, ours = graphs(reference_node, manifests)
    assert [(n.depth, n.order_name) for n in ours] == [
        (n.depth, n.order_name)
        for n in sorted(ref.values(), key=lambda n: (n.depth, n.order_name))]


def test_test_addon_without_anchor_rejects_both_graphs(reference_node):
    ref, ours = graphs(reference_node, {'test_empty': {'depends': []}})
    for node in (ref['test_empty'], ours['test_empty']):
        with pytest.raises(ValueError):
            _ = node.depth


def test_test_addon_cycle_still_has_domain_error(reference_node):
    _, ours = graphs(reference_node, {'test_cycle': {'depends': ['a']},
                                     'a': {'depends': ['test_cycle']}})
    with pytest.raises(ValueError, match='ModuleGraphCycle'):
        _ = ours['test_cycle'].order_name


def test_mutating_anchor_dependencies_invalidates_order(reference_node):
    _, ours = graphs(reference_node, {'base': {'depends': []},
        'test_base': {'depends': ['base']}, 'a': {'depends': ['base']}})
    assert ours.order() == ['base', 'test_base', 'a']
    ours['test_base'].depends[:] = ['a']
    assert ours['test_base'].depth == 1
    assert ours['test_base'].order_name == 'a test_base'
    assert ours.order() == ['base', 'a', 'test_base']


def test_phase_rejects_invalid_mode_and_keeps_cycle_diagnostic(reference_node):
    with pytest.raises(ValueError, match='mode'):
        ModuleGraph(mode='unknown')
    graph = ModuleGraph(mode='update')
    assert graph.mode == 'update'
    _, ours = graphs(reference_node, {'a': {'depends': ['b']},
                                     'b': {'depends': ['a']}})
    ours.mode = 'update'
    with pytest.raises(ValueError, match='ModuleGraphCycle'):
        _ = ours['a'].phase


def test_update_phase_without_dependency_anchor_matches_reference(reference_node):
    ref, ours = graphs(reference_node, {'standalone': {'depends': []}})
    ref['standalone'].module_graph.mode = ours.mode = 'update'
    for node in (ref['standalone'], ours['standalone']):
        with pytest.raises(ValueError):
            _ = node.phase


@pytest.mark.parametrize('log_dependents', [True, False])
def test_recursive_removal_matches_reference(reference_node, reference_graph, caplog, log_dependents):
    nodes, ours = graphs(reference_node, {'base': {'depends': []},
        'left': {'depends': ['base']}, 'right': {'depends': ['base']},
        'diamond': {'depends': ['left', 'right']}, 'independent': {'depends': []}})
    ref = reference_graph(None)
    # Hold input mapping order constant: this test qualifies removal, not the
    # different explicit/transitive population policy of extend().
    ref._modules = {name: nodes[name] for name in ours._nodes}
    caplog.set_level(logging.INFO)
    ref._remove('base', log_dependents=log_dependents)
    expected_logs = [r.getMessage() for r in caplog.records]
    caplog.clear()
    ours._remove('base', log_dependents=log_dependents)
    assert list(ours._nodes) == list(ref._modules) == ['independent']
    assert [r.getMessage() for r in caplog.records] == expected_logs


def test_removing_absent_node_rejects_both_graphs(reference_graph):
    for graph in (reference_graph(None), ModuleGraph()):
        with pytest.raises(KeyError):
            graph._remove('absent')


def test_missing_dependency_prunes_dependents_and_retains_independent_node(reference_node, reference_graph):
    nodes, ours = graphs(reference_node, {'base': {'depends': []},
        'child': {'depends': ['base']}, 'grandchild': {'depends': ['child']},
        'independent': {'depends': []}})
    ref = reference_graph(None)
    ref._modules = nodes
    ref._modules.pop('base')
    ours._nodes.pop('base')
    names = ['child', 'grandchild', 'independent']
    ref._update_depends(names)
    ours._update_depends(names)
    assert list(ours._nodes) == list(ref._modules) == ['independent']


def test_explicit_depth_preparation_prunes_cycles_like_reference(reference_node, reference_graph):
    nodes, ours = graphs(reference_node, {'a': {'depends': ['b']},
        'b': {'depends': ['a']}, 'child': {'depends': ['a']},
        'independent': {'depends': []}})
    ref = reference_graph(None)
    ref._modules = nodes
    names = list(nodes)
    ref._update_depth(names)
    ours._update_depth(names)
    assert list(ours._nodes) == list(ref._modules) == ['independent']


@pytest.mark.parametrize('column_present', [False, True])
def test_reference_imported_modules_optional_column_and_cache(reference_graph, column_present):
    """Reference-only fixture: does not qualify Consumer DB import support."""
    cursor = Mock()
    cursor.fetchall.return_value = [('custom_import',), ('studio_customization',)]
    probe = Mock(return_value=column_present)
    # Preserve insertion/deduplication for this bounded adapter; no assertion
    # about the full native OrderedSet class or PostgreSQL execution.
    with patch.dict(reference_graph._imported_modules.func.__globals__, {
            'column_exists': probe,
            'OrderedSet': lambda names: list(dict.fromkeys(names))}):
        graph = reference_graph(cursor)
        expected = ['studio_customization', 'custom_import'] if column_present else ['studio_customization']
        assert list(graph._imported_modules) == expected
        assert list(graph._imported_modules) == expected
        probe.assert_called_once_with(cursor, 'ir_module_module', 'imported')
        if column_present:
            cursor.execute.assert_called_once_with('SELECT name FROM ir_module_module WHERE imported')
            cursor.fetchall.assert_called_once_with()
        else:
            cursor.execute.assert_not_called()
            cursor.fetchall.assert_not_called()
