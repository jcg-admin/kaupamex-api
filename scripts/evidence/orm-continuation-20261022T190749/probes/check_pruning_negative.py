"""Run current pruning controls against the published pre-change Consumer.

Only in-process classes are substituted; no checkout or source mutation.
Expected pytest exit is1. This is a negative verification, not a suite PASS.
"""
import subprocess
import types

import pytest

from modules import module_graph

source = subprocess.check_output([
    'git', 'show', '0d91ce3e494a09d27868998d48bec96a75480ca3:src/modules/module_graph.py',
], text=True)
baseline = types.ModuleType('module_graph_before_pruning')
exec(compile(source, 'published-module-graph-before-pruning', 'exec'), baseline.__dict__)
# The ordinary test fixture patches the canonical manifest function. Preserve
# that same input seam for the baseline class, without changing its methods.
baseline.load_manifest = lambda name: module_graph.load_manifest(name)
module_graph.ModuleGraph = baseline.ModuleGraph
raise SystemExit(pytest.main([
    '-q', 'scripts/workbench/odoo-orm-reference-inventory-20260910T181517/tests/test_module_graph_contract.py',
    '--confcutdir=scripts/workbench', '-k',
    'recursive_removal or removing_absent or missing_dependency_prunes or explicit_depth_preparation',
]))
