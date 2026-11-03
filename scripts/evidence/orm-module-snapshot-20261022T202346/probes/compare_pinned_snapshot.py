"""Comparación de cuerpos fijados con las mismas filas PostgreSQL; no Odoo nativo."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import django

django.setup()

from django.conf import settings
from django.db import connection, transaction
from addons.base.models.ir_module import IrModule
from modules.module_graph import ModuleGraph

assert settings.DATABASES['default']['NAME'].startswith('orm_bootstrap_')
source = Path.cwd()/'scripts/workbench/odoo-orm-reference-inventory-20260910T181517/tests/test_module_graph_contract.py'
spec = importlib.util.spec_from_file_location('pinned_contract_owner', source)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
ReferenceGraph = owner.reference_graph.__wrapped__()
ReferenceNode = owner.reference_node.__wrapped__()
manifests = {'base': {'depends': [], 'installable': True},
             'snapshot_child': {'depends': ['base'], 'installable': True},
             'snapshot_independent': {'depends': [], 'installable': True}}


class RecordedRows:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, query, parameters):
        assert 'latest_version AS installed_version' in query
        assert set(parameters[0]) == set(manifests)

    def fetchall(self):
        return self.rows


with connection.schema_editor() as editor:
    editor.create_model(IrModule)
count = 0
for mode in ('load', 'update'):
    for state in ('installed', 'to upgrade', 'to remove', 'to install', 'uninstalled', 'uninstallable'):
        with transaction.atomic():
            IrModule.objects.bulk_create([
                IrModule(name=name, state=state if name == 'base' else 'installed',
                         version='manifest-new', installed_version='installed-old' if name == 'base' else None,
                         demo=name == 'base') for name in manifests])
            rows = list(IrModule.objects.order_by('pk').values_list('name', 'pk', 'state', 'demo', 'installed_version'))
            reference = ReferenceGraph(RecordedRows(rows), mode=mode)
            for name, manifest in manifests.items():
                node = object.__new__(ReferenceNode)
                node.name, node.manifest, node.module_graph = name, manifest, reference
                node.id, node.state, node.demo = 0, 'uninstalled', False
                node.installed_version = node.load_version = None
                node.load_state = 'uninstalled'
                reference._modules[name] = node
            for name, manifest in manifests.items():
                reference[name].depends = [reference[d] for d in manifest['depends']]
            reference._update_from_database(tuple(manifests))
            with patch('modules.module_graph.load_manifest', side_effect=manifests.__getitem__):
                consumer = ModuleGraph.from_database(list(manifests), using='default', mode=mode)
            assert len(reference) == len(consumer)
            fields = ('id', 'state', 'demo', 'installed_version', 'load_version', 'load_state')
            for name in manifests:
                assert (name in reference) == (name in consumer)
                if name in reference:
                    assert tuple(getattr(reference[name], f) for f in fields) == tuple(getattr(consumer[name], f) for f in fields)
            transaction.set_rollback(True)
        count += 1
        print('PASS pinned differential', mode, state)
print(f'{count} pinned differential cases PASS; unchanged reference body with recorded DB rows, no Odoo native cursor/runtime acceptance')
