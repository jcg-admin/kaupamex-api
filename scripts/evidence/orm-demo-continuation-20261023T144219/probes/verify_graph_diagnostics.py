"""Contrasta diagnósticos con cuerpos Odoo fijados; requiere Django listo.

Se ejecuta desde el shell nativo de Django, no inicializa otro runtime.
El cursor de referencia y el queryset Consumer son adaptadores de prueba.
"""

import ast
from collections.abc import Iterable
import hashlib
import json
import logging
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, patch

from modules import module_graph
from reference_roots import TOOLS_ROOT, tree

REVISION = 'abe4040ec1a45beee90fb694e4eae4453e46b389'
REFERENCE = tree('odoo19c').resolve() / 'odoo/modules/module_graph.py'
REPOSITORY = TOOLS_ROOT.resolve()
RELATIVE = REFERENCE.relative_to(REPOSITORY)
SOURCE = subprocess.check_output(
    ['git', '-C', str(REPOSITORY), 'show', f'{REVISION}:{RELATIVE}']
)
REFERENCE_AST = ast.parse(SOURCE)
REFERENCE_CLASS = next(
    node for node in REFERENCE_AST.body
    if isinstance(node, ast.ClassDef) and node.name == 'ModuleGraph'
)
METHOD_NAMES = {
    '__init__', '__contains__', '__getitem__', '_remove',
    '_update_from_database',
}
REFERENCE_CLASS.body = [
    node for node in REFERENCE_CLASS.body
    if isinstance(node, ast.FunctionDef) and node.name in METHOD_NAMES
]
assert {node.name for node in REFERENCE_CLASS.body} == METHOD_NAMES
EXTRACTED = ast.Module(
    body=[
        ast.ImportFrom(
            module='__future__',
            names=[ast.alias(name='annotations')],
            level=0,
        ),
        REFERENCE_CLASS,
    ],
    type_ignores=[],
)
ast.fix_missing_locations(EXTRACTED)
REFERENCE_LOGGER = logging.getLogger('contract_reference_graph_diagnostics')
NAMESPACE = {'_logger': REFERENCE_LOGGER, 'Iterable': Iterable}
exec(compile(EXTRACTED, str(RELATIVE), 'exec'), NAMESPACE)


class LogCapture(logging.Handler):
    """Conserva nivel y mensaje observable sin depender de la VM."""

    def __init__(self):
        super().__init__()
        self.rows = []

    def emit(self, record):
        self.rows.append([record.levelname, record.getMessage()])


def capture(logger, operation):
    """Restaura la configuración del logger aun cuando falle el contraste."""
    handler = LogCapture()
    level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        operation()
        return handler.rows
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)


def verify_case(state, mode):
    """Mantiene alias, filas y dependencias equivalentes en ambos grafos."""
    rows = [
        ('root', 1, state, False, None),
        ('child', 2, 'installed', False, '1.0'),
    ]
    cursor = Mock()
    cursor.fetchall.return_value = rows
    reference = NAMESPACE['ModuleGraph'](cursor, mode)
    root = SimpleNamespace(name='root', depends=[])
    child = SimpleNamespace(name='child', depends=[root])
    reference._modules = {'root': root, 'child': child}
    reference_logs = capture(
        REFERENCE_LOGGER,
        lambda: reference._update_from_database(['root', 'child']),
    )
    manifests = {
        'root': {'depends': [], 'installable': True},
        'child': {'depends': ['root'], 'installable': True},
    }
    model = Mock()
    query = model.objects.using.return_value.filter.return_value
    query.order_by.return_value.values_list.return_value = rows
    with (
        patch.object(module_graph, 'load_manifest', manifests.__getitem__),
        patch.object(module_graph.apps, 'get_model', return_value=model),
        patch(
            'django.db.backends.base.base.BaseDatabaseWrapper.'
            'ensure_connection',
            side_effect=AssertionError('No se permite SQL en este contraste'),
        ),
    ):
        consumer = module_graph.ModuleGraph(mode=mode)
        consumer.extend(['root', 'child'])
        consumer_logs = capture(
            module_graph._logger,
            lambda: consumer._update_from_database(
                ['root', 'child'], using='contract_catalogue'
            ),
        )
    assert consumer_logs == reference_logs
    assert sorted(consumer._nodes) == sorted(reference._modules)
    for name in consumer._nodes:
        expected = reference._modules[name]
        actual = consumer[name]
        assert (actual.state, actual.load_state) == (
            expected.state, expected.load_state,
        )
        assert actual.installed_version == expected.installed_version
    model.objects.using.assert_called_once_with('contract_catalogue')
    return {
        'state': state, 'mode': mode, 'messages': consumer_logs,
        'remaining_nodes': sorted(consumer._nodes), 'status': 'PASS',
    }


cases = [
    verify_case(state, mode)
    for state in ('uninstallable', 'uninstalled', 'to install')
    for mode in ('load', 'update')
]
result = {
    'reference_revision': REVISION,
    'reference_path': (
        f'odoo19c:{REFERENCE.relative_to(tree("odoo19c").resolve())}'
    ),
    'reference_sha256': hashlib.sha256(SOURCE).hexdigest(),
    'consumer_sha256': hashlib.sha256(
        Path(module_graph.__file__).read_bytes()
    ).hexdigest(),
    'cases': cases,
    'scope': 'Cuerpos de referencia con adaptadores; no runtime Odoo nativo',
    'sql': 'Bloqueado; sin aceptación física ni de persistencia',
    'acceptance': 'No acredita procedencia imported ni el cargador completo',
}
output = Path(__file__).resolve().parents[1] / 'outputs'
(output / 'graph-diagnostics-reference-comparison.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n'
)
print(json.dumps(result, ensure_ascii=False, indent=2))
