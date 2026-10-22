"""Bounded differential verification, not native Odoo loader acceptance."""
import __future__
import ast
import functools
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

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


def graphs(reference_node, manifests):
    reference = {}
    for name in manifests:
        node = object.__new__(reference_node)
        node.name = name
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


def test_ordinary_depth_agrees_but_order_key_does_not(reference_node):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
                                      'sale': {'depends': ['base']}})
    assert [ref[n].depth for n in ('base', 'sale')] == [0, 1]
    assert [ours[n].depth for n in ('base', 'sale')] == [0, 1]
    assert ref['sale'].order_name == 'sale'
    assert ours['sale'].order_name == '001-sale'


def test_test_addon_placement_is_not_equivalent(reference_node):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
        'aaa': {'depends': ['base']}, 'test_base': {'depends': ['base']}})
    assert ref['test_base'].depth == 0
    assert ours['test_base'].depth == 1
    assert ref['test_base'].order_name == 'base test_base'
    assert [n.name for n in sorted(ref.values(), key=lambda n: (n.depth, n.order_name))] == ['base', 'test_base', 'aaa']
    assert ours.order() == ['base', 'aaa', 'test_base']


def test_reference_phase_depends_on_mode_and_pending_state(reference_node):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
        'sale': {'depends': ['base']}, 'bridge': {'depends': ['sale']}})
    assert ref['base'].phase == 0
    assert ref['sale'].phase == ref['bridge'].phase == 1
    for node in ref.values():
        node.__dict__.pop('phase', None)
        node.module_graph.mode = 'update'
    ref['sale'].state = 'to install'
    assert ref['sale'].phase == 2
    assert ref['bridge'].phase == 3
    assert not hasattr(ours['sale'], 'phase')


def test_demo_eligibility_is_dependency_based(reference_node):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
                                      'sale': {'depends': ['base']}})
    assert ref['base'].demo_installable is True
    assert ref['sale'].demo_installable is False
    ref['base'].demo = True
    assert ref['sale'].demo_installable is True
    assert not hasattr(ours['sale'], 'demo_installable')


def test_static_graph_membership_lookup_and_cardinality(reference_node):
    ref, ours = graphs(reference_node, {'base': {'depends': []},
                                      'sale': {'depends': ['base']}})
    assert len(ours) == len(ref) == 2
    assert 'sale' in ours
    assert 'absent' not in ours
    assert ours['sale'].name == ref['sale'].name
    with pytest.raises(KeyError):
        ours['absent']
