"""Comprueba lectura incremental real sin instalar módulos ni migrar datos."""
import copy
import importlib.util
from pathlib import Path
import json
import os
import sys
from unittest import mock

import django

django.setup()

from django.conf import settings
from django.db import connections
from django.test.utils import CaptureQueriesContext
from modules.module_graph import ModuleGraph
from tools.misc import OrderedSet
from tools.func import reset_cached_properties

assert os.environ['DB_QA_NAME'].startswith('orm_bootstrap_')
connection = connections['default']
other = 'incremental_graph_other'
settings.DATABASES[other] = copy.deepcopy(settings.DATABASES['default'])
settings.DATABASES[other]['OPTIONS']['options'] = '-c search_path=incremental_graph_other'
connections.databases[other] = settings.DATABASES[other]
with connection.cursor() as cursor:
    cursor.execute('CREATE SCHEMA incremental_graph_other')
    for schema, start, state, demo, version in [
        ('public', 1, 'uninstalled', True, 'database-A'),
        ('incremental_graph_other', 11, 'installed', False, 'database-B'),
    ]:
        cursor.execute('CREATE TABLE %s.ir_module_module ('
                       'id integer PRIMARY KEY, name varchar(128), state varchar(32), '
                       'demo boolean, installed_version varchar(128))' % schema)
        cursor.execute('INSERT INTO %s.ir_module_module VALUES '
                       '(%%s, %%s, %%s, %%s, %%s), (%%s, %%s, %%s, %%s, %%s)' % schema,
                       [start, 'base', 'installed', demo, version,
                        start + 1, 'child', state, demo, version])

manifests = {
    'base': {'depends': [], 'installable': True},
    'child': {'depends': ['base'], 'installable': True},
    'blocked': {'depends': ['child'], 'installable': True},
    'disabled': {'depends': ['base'], 'installable': False},
    'cycle_a': {'depends': ['cycle_b'], 'installable': True},
    'cycle_b': {'depends': ['cycle_a'], 'installable': True},
}
original_extend = ModuleGraph.extend
original_snapshot = ModuleGraph._update_from_database


def wrong_alias_snapshot(graph, names, *, using):
    """Inyecta una lectura del catálogo incorrecto sin cambiar el producto."""
    return original_snapshot(graph, names, using='default')



def annul_extension(graph, names):
    """Anula sólo la preparación de ampliaciones posteriores al snapshot."""
    using = graph.using
    if graph._nodes:
        graph.using = None
    try:
        return original_extend(graph, names)
    finally:
        graph.using = using


cases = []
try:
    with mock.patch('modules.module_graph.load_manifest', manifests.__getitem__):
        with mock.patch.object(ModuleGraph, 'extend',
                               annul_extension if '--annul' in sys.argv else original_extend), \
                mock.patch.object(ModuleGraph, '_update_from_database',
                                  wrong_alias_snapshot if '--wrong-alias' in sys.argv else original_snapshot):
            first = ModuleGraph.from_database(['base'], using='default')
            second = ModuleGraph.from_database(['base'], using=other)
            first.extend(['child'])
            second.extend(['child'])
            assert 'child' not in first, 'uninstalled child was incorrectly selected'
            assert 'child' in second, 'selected catalogue was not used for extension'
            assert (second['child'].id, second['child'].demo,
                    second['child'].load_version) == (12, False, 'database-B')
            cases.append('catalogue alias, installed-state selection, identity/demo/version')
            first.extend(['blocked'])
            assert set(first._nodes) == {'base'}
            cases.append('new dependent removed with uninstalled dependency')
            with connection.cursor() as cursor:
                cursor.execute("UPDATE ir_module_module SET state='to install' WHERE name='child'")
            update = ModuleGraph.from_database(['base'], using='default', mode='update')
            update['base'].state = 'to upgrade'
            with CaptureQueriesContext(connection) as queries:
                update.extend(['child'])
            assert len(queries) == 1
            assert queries[0]['sql'].lstrip().upper().startswith('SELECT')
            assert (update['child'].id, update['child'].state, update['child'].demo,
                    update['child'].installed_version, update['child'].load_version) == (
                        2, 'to install', True, 'database-A', 'database-A')
            assert update['child'].phase == 2
            assert (update['base'].state, update['base'].load_state) == ('to upgrade', 'installed')
            cases.append('new snapshot, update phase, loaded snapshot preserved; SELECT only')
            with CaptureQueriesContext(connection) as queries:
                update.extend(['child', 'base'])
            assert len(queries) == 0
            cases.append('duplicate extension performs no catalogue query')
            update.extend(['disabled', 'cycle_a'])
            assert set(update._nodes) == {'base', 'child'}
            cases.append('uninstallable manifest and new cycle pruned')
            if '--differential' in sys.argv:
                source = Path('scripts/workbench/odoo-orm-reference-inventory-20260910T181517/tests/test_module_graph_contract.py')
                spec = importlib.util.spec_from_file_location('existing_pinned_graph_owner', source)
                owner = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(owner)
                reference_graph = owner.reference_graph.__wrapped__()
                reference_node = owner.reference_node.__wrapped__()

                class FixtureManifest(dict):
                    @classmethod
                    def for_addon(cls, name, **kwargs):
                        return cls(manifests[name])

                    def raw_value(self, key):
                        return self

                class CursorAdapter:
                    def __init__(self, cursor):
                        self.cursor = cursor

                    def execute(self, query, parameters):
                        # Adapta sólo el protocolo SQL de cursor y el nombre de columna.
                        query = query.replace('latest_version AS installed_version', 'installed_version')
                        query = query.replace('WHERE name IN %s', 'WHERE name = ANY(%s)')
                        self.cursor.execute(query, [list(parameters[0])])

                    def fetchall(self):
                        return self.cursor.fetchall()

                reference_node.__init__.__globals__.update(Manifest=FixtureManifest, OrderedSet=OrderedSet)
                namespace = reference_graph.extend.__globals__
                namespace.update(ModuleNode=reference_node, OrderedSet=OrderedSet,
                                 reset_cached_properties=reset_cached_properties,
                                 column_exists=lambda *args: False)
                fields = ('id', 'state', 'demo', 'installed_version', 'load_version', 'load_state')
                differential_count = 0
                with connection.cursor() as cursor:
                    for mode in ('load', 'update'):
                        for state in ('installed', 'to upgrade', 'to remove', 'to install',
                                      'uninstalled', 'uninstallable'):
                            cursor.execute("UPDATE ir_module_module SET state=%s WHERE name='child'", [state])
                            pinned = reference_graph(CursorAdapter(cursor), mode=mode)
                            pinned.extend(['base'])
                            consumer = ModuleGraph.from_database(['base'], using='default', mode=mode)
                            pinned['base'].state = consumer['base'].state = 'to upgrade'
                            pinned.extend(['child'])
                            consumer.extend(['child'])
                            assert set(pinned._modules) == set(consumer._nodes)
                            for name in consumer._nodes:
                                assert tuple(getattr(pinned[name], field) for field in fields) == tuple(
                                    getattr(consumer[name], field) for field in fields)
                            assert [node.name for node in pinned] == consumer.order()
                            differential_count += 1
                    cursor.execute("UPDATE ir_module_module SET state='to install' WHERE name='child'")
                cases.append('%s incremental pinned-body differential cases' % differential_count)

    with connection.cursor() as cursor:
        cursor.execute('SELECT name,state,demo,installed_version FROM ir_module_module ORDER BY id')
        assert cursor.fetchall() == [('base', 'installed', True, 'database-A'),
                                     ('child', 'to install', True, 'database-A')]
    cases.append('catalogue unchanged by graph preparation')
    print(json.dumps({'result': 'PASS', 'cases': cases,
                      'limit': 'Two schemas in one owned database, not N>1 installation acceptance'},
                     ensure_ascii=False), flush=True)
finally:
    connections[other].close()
    connection.close()
