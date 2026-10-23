"""Anulación aislada: sin cómputo/guarda, los controles deben fallar."""
import django
django.setup()
from modules.module_graph import ModuleGraph
import pytest

ModuleGraph._depth = lambda self, node, memo, path: memo.setdefault(node.name, 0)
raise SystemExit(pytest.main(['--confcutdir=tests/unit/modules', '-o', 'addopts=',
                             '--tb=short', '-q', 'tests/unit/modules/test_module_graph.py']))
