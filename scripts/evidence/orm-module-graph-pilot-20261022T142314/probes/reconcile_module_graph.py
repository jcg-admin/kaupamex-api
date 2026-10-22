"""Focalized Consumer reconciliation; reuse the existing inventory unchanged.

This is not a general extractor or a second correspondence resolver. The
dispositions and supplemental source review below concern one pinned file.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[4]
RUN = Path(__file__).resolve().parents[1]
INVENTORY = REPO / 'scripts/workbench/odoo-orm-reference-inventory-20260910T181517'
sys.path.insert(0, str(REPO / 'scripts'))
from counterpart_body import declarations_of  # noqa: E402
from reference_roots import ADDON_ALIAS, addon_root, tree  # noqa: E402

spec = importlib.util.spec_from_file_location('existing_inventory', INVENTORY / 'inventory_reference_orm.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)
reference = tree('odoo19c') / 'odoo/modules/module_graph.py'
consumer = REPO / 'src/modules/module_graph.py'
revision = 'abe4040ec1a45beee90fb694e4eae4453e46b389'

# Source-reviewed dispositions, not a new name-resolution algorithm.
dispositions = {
 'ModuleNode': ('modules.module_graph.ModuleNode', 'partial node; no loader-state attributes'),
 'ModuleNode.__init__': ('ModuleNode.__init__; IrModule persisted catalogue', 'manifest/dependency node only; catalogue does not supply graph load snapshot'),
 'ModuleNode.order_name': ('ModuleNode.order_name', 'verified different ordinary key and test_* placement'),
 'ModuleNode.depth': ('ModuleNode.depth; ModuleGraph._depth', 'ordinary depth agrees; test_* depth differs'),
 'ModuleNode.phase': (None, 'pending mode/state-dependent loading phases; migrations are not equivalent'),
 'ModuleNode.demo_installable': (None, 'pending dependency demo eligibility in loader'),
 'ModuleGraph': ('modules.module_graph.ModuleGraph', 'static dependency graph; not database-bound loader'),
 'ModuleGraph.__init__': ('ModuleGraph.__init__', 'no cursor/alias or load/update mode; pending execution context'),
 'ModuleGraph.__contains__': ('ModuleGraph.__contains__', 'membership present; bounded test below, no whole graph equivalence'),
 'ModuleGraph.__getitem__': ('ModuleGraph.__getitem__', 'lookup present; bounded test below'),
 'ModuleGraph.__iter__': ('ModuleGraph.__iter__', 'verified different test_* ordering; phases not represented'),
 'ModuleGraph.__len__': ('ModuleGraph.__len__', 'cardinality present; bounded test below'),
 'ModuleGraph.extend': ('ModuleGraph.extend; IrModule._request_install', 'transitive static expansion versus explicit nodes then state filtering; requests do not execute loading'),
 'ModuleGraph._imported_modules': (None, 'pending database-imported modules/studio_customization handling; importability not equivalence'),
 'ModuleGraph._update_depends': ('ModuleGraph.extend/missing; IrModule dependency validation', 'partial distributed validation; no reference dependent-node removal contract'),
 'ModuleGraph._update_depth': ('ModuleGraph._depth/cycles', 'cycle rejection tested previously; reference removes invalid nodes rather than raising domain cycle error'),
 'ModuleGraph._update_from_database': ('IrModule catalogue; update_module_list; administrative requests', 'states persist per database; no graph snapshot or load/update filtering proven'),
 'ModuleGraph._remove': (None, 'pending recursive dependent exclusion from executable graph'),
}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    # Both extraction and signature representation are the historical tool's.
    records = inventory.declared_symbols(reference)
    declarations = {(d.owner, d.name): d for d in declarations_of(reference)}
    rows = []
    for record in records:
        name = '.'.join(filter(None, [record['owner'], record['name']]))
        counterpart, disposition = dispositions[name]
        declaration = declarations[(record['owner'] or '', record['name'])]
        # Preserve actual source header instead of inventing a richer signature
        # extractor. Annotated defaults remain reviewable in this source excerpt.
        header = reference.read_text().splitlines()[declaration.lineno - 1]
        rows.append({**record, 'qualified_name': name,
            'source_header': header, 'counterpart': counterpart,
            'disposition': disposition, 'task': 'TASK-API-0382',
            'acceptance': 'not_verified',
            'verification': 'tests/test_module_graph_contract.py; pilot.junit.xml; earlier module lifecycle evidence; otherwise not_verified'})
        rows[-1]['contract_14_elements'] = {
            'reference_revision': revision,
            'reference_symbol': 'odoo/modules/module_graph.py::' + name,
            'behavior': disposition,
            'execution_flow': 'Manifest -> graph dependency construction -> database state/filtering -> ordered loader; Consumer currently stops at static graph and queued requests',
            'inputs_outputs': header,
            'side_effects': 'Reference may read database/prune graph/cache properties; Consumer catalogue requests persist state separately; no demonstrated loader execution',
            'dependencies': ['TASK-API-0382', 'Manifest parser', 'selected database catalogue', 'effective registry; schema/data/hooks where execution is required'],
            'consumers': ['ModuleGraph iteration/extend', 'module loading; registry construction'],
            'installed_mechanism': counterpart,
            'existing_adaptation': 'Static Consumer graph and database-owned IrModule requests, native Django persistence/transactions; not equivalent to loader automatically',
            'verification': rows[-1]['verification'],
            'equivalence': 'not_verified except bounded observations explicitly asserted in pilot tests',
            'limitations': 'No native Odoo DB fixtures; no new production implementation; class presence is not acceptance',
            'integration': 'PR109 pending; TASK-API-0382 unchanged; no merge/acceptance'}
    assert len(rows) == len(dispositions) == 18
    dump(INVENTORY / 'outputs/module-graph-pilot.json', {
        'reference_revision': revision, 'reference_file': 'odoo/modules/module_graph.py',
        'consumer_revision': subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
        'consumer_sha256': hashlib.sha256(consumer.read_bytes()).hexdigest(),
        'instrument': str(INVENTORY.relative_to(REPO) / 'inventory_reference_orm.py') + ':file_inventory/declared_symbols',
        'reference_inventory': inventory.file_inventory(reference),
        'consumer_inventory': inventory.file_inventory(consumer),
        'correspondence': rows,
        'supplemental_source_review': {
            'method': 'Manual review of complete pinned source; no additional AST extractor',
            'nested_definitions': [{'qualified_name': 'ModuleNode.phase.not_in_the_same_phase',
                'signature': '(module: ModuleNode, dependency: ModuleNode) -> bool',
                'behavior': "XOR of state == 'to install'; executed by phase test",
                'counterpart': None, 'task': 'TASK-API-0382', 'acceptance': 'not_verified'}],
            'classes_bases': {'ModuleNode': [], 'ModuleGraph': []},
            'imports': ['__future__.annotations', 'functools', 'logging', 'typing',
                'odoo.tools.reset_cached_properties', 'odoo.tools.OrderedSet',
                'odoo.tools.sql.column_exists', '.module.Manifest'],
            'type_checking_imports': ['collections.abc.Collection', 'collections.abc.Iterable',
                'collections.abc.Iterator', 'collections.abc.Mapping', 'typing.Literal', 'odoo.sql_db.BaseCursor'],
            'assignments': {'STATES': "TYPE_CHECKING Literal['uninstalled','uninstallable','installed','to install','to upgrade','to remove']",
                '_logger': 'logging.getLogger(__name__)'},
            'exports': 'No explicit __all__; imports are not locally defined contracts',
            'instance_attributes': {
                'ModuleNode': ['name','manifest','id','state','demo','installed_version','load_state','load_version','depends','module_graph'],
                'ModuleGraph': ['mode','_modules','_cr']},
            'local_bindings': 'Parameters, loop/comprehension targets, local variables and lambda parameters remain in complete source; not separate public contract identities',
            'overloads_classmethods_staticmethods': 'None in this file; cached_property/property decorators preserved above'},
        'consumer_only': ['ModuleGraphCycle','ModuleGraphCycle.__init__','ModuleNode.__repr__',
            'ModuleGraph._depth','ModuleGraph.missing','ModuleGraph.cycles',
            'ModuleGraph.cycles.walk','ModuleGraph.auto_installable','ModuleGraph.order',
            'ModuleGraph.__repr__','build_graph','ModuleNode.__slots__'],
        'limits': ['Historical extractor excludes nested functions, imports, assignments, bases and full annotation/default values; supplemented manually for this one file',
            'Read/parse failure can silently return empty; this run requires actual 18 expected declarations',
            'Signature name/default-flag equality and substantive body are not semantic proof',
            'No general exhaustive inventory beyond this pilot; no global contract acceptance'],
        'counts': {'reference_extractor_occurrences': 18,'additional_nested_function': 1,
            'defined_classes_and_callables_reviewed': 19,'contract_denominator': 'Not symbol count; acceptance not_verified'},
        'evidence': str(RUN.relative_to(REPO))})
    # Resolver authority already distinguishes the family aliases from authz.
    cache = inventory.TREE_ROOTS['odoo19c']
    while not (cache / '.git').exists():
        if cache == cache.parent:
            raise RuntimeError('Pinned Git checkout unavailable')
        cache = cache.parent
    paths = [str((tree()/p/'auth').relative_to(cache)) for p in ('addons','odoo/addons')]
    command = ['git','-C',str(cache),'ls-tree',revision,'--',*paths]
    git_tree = subprocess.run(command,text=True,capture_output=True,check=True)
    dump(RUN / 'outputs/namespace-authority.json', {
        'authority': 'scripts/reference_roots.py:ADDON_ALIAS/addon_root',
        'existing_aliases': ADDON_ALIAS,
        'authz_reference_resolution': str(addon_root('authz')),
        'literal_auth_in_materialized_reference': {str(root.relative_to(tree())): (root/'auth').exists()
            for root in (tree()/'addons', tree()/'odoo/addons')},
        'git_tree_check': {'command':command,'exit_code':git_tree.returncode,'stdout':git_tree.stdout,'stderr':git_tree.stderr},
        'interpretation': 'Pinned Git tree has no literal auth addon at either Community root. No blanket auth->authz alias in current resolver. Family aliases are existing adaptations; authz is a separate capability implementation, not a literal addon rename.',
        'consumer_mechanisms': ['addons/authz/apps.py:AuthzConfig.name=addons.authz',
            'addons/authz/__manifest__.py:depends base; auto_install True',
            'src/config/settings/base.py:AUTH_USER_MODEL=base.ResUsers',
            'src/addons/base/migrations/0001_initial.py:authz.0001_initial dependency'],
        'functional_equivalence': 'not_verified; existing base->authz bootstrap cycle TASK-API-0173 and capability security obligations remain separate',
        'renames_performed': False})


if __name__ == '__main__':
    main()
