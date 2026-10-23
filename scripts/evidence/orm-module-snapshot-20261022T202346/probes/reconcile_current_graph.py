"""Actualiza la conciliación existente; reutiliza extracción y referencia por hash."""
import hashlib
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RUN = Path(__file__).resolve().parents[1]
prior = REPO/'scripts/evidence/orm-continuation-20261022T190749/probes/reconcile_current_graph.py'
spec = importlib.util.spec_from_file_location('existing_reconciliation', prior)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
owner.RUN = RUN
verification = '20PostgreSQL snapshot/preparation controls;12pinned-body differential cases;two-database alias/demo/version isolation;version migration forward/reverse and3catalogue controls'
remaining = 'Read-only graph preparation, not execution of schema/data/hooks, installed-version finalization, effective registry or worker consistency. Official0382 pending, no merge or acceptance.'
mechanisms = {
 'ModuleNode':'ModuleNode snapshot attributes; IrModule.installed_version nullable persistence; explicit from_database preparation',
 'ModuleNode.__init__':'ModuleNode.__init__ initializes id0, state/load_state uninstalled, demoFalse and both version snapshotsNone',
 'ModuleNode.phase':'ModuleGraph._phase consumes mode and explicit state; from_database populates state from selected alias',
 'ModuleNode.demo_installable':'Dependency node.demo flags now populated from the selected database; no demo data load',
 'ModuleGraph':'ModuleGraph.from_database -> transitive manifest closure -> explicit dependency/depth preparation -> selected DB snapshot -> ordering',
 'ModuleGraph.__init__':'Static default constructor retained; mode validated; usingNone until explicit from_database factory binds alias',
 'ModuleGraph.__iter__':'Phase/depth/dependency ordering reads retained database snapshot nodes; two actual databases produce different load orders',
 'ModuleGraph.extend':'Static transitive closure retained for administrative requests; from_database composes preparation/filtering, not literal reference extend equivalence',
 'ModuleGraph._update_depends':'Existing pure preparation now used by from_database; dependency pruning precedes the snapshot',
 'ModuleGraph._update_depth':'Existing cycle pruning now used only by explicit from_database preparation; static request cycle rejection retained',
 'ModuleGraph._update_from_database':'Django apps.get_model(base,IrModule).objects.using(explicit_alias).filter(name__in=...).values_list(name,id,state,demo,installed_version); one read query; skip/prune according to mode; copy load snapshots',
 'ModuleGraph._remove':'Recursive in-memory pruning used by explicit preparation and database state filter; no persistent state change',
}
for name, mechanism in mechanisms.items():
 behavior, _, _, _ = owner.REVIEW[name]
 owner.REVIEW[name] = behavior, mechanism, verification, remaining
owner.main()
output = owner.INVENTORY/'outputs/module-graph-contract-reconciliation.json'
d = json.loads(output.read_text())
history = json.loads((owner.INVENTORY/'outputs/module-graph-pilot.json').read_text())
rows = {r['qualified_name']:r for r in history['correspondence']}
for row in d['contract_records']:
 name = row['reference_symbol'].split('::',1)[1]
 old = rows.get(name)
 if old:
  row['source_location'] = old['lineno']
  row['symbol_kind'] = old['kind']
  row['owner'] = old.get('owner') or 'odoo.modules.module_graph'
  row['inputs_outputs'] = {'source_header':old['source_header'],'signature':old.get('signature'),'decorators':old.get('decorators',[]),'behavior':row['behavior']}
 else:
  row['owner'] = 'ModuleNode.phase'
  row['symbol_kind'] = 'nested_function'
  source = owner.inventory.TREE_ROOTS['odoo19c']/'odoo/modules/module_graph.py'
  row['source_location'] = next(i for i,s in enumerate(source.read_text().splitlines(),1) if 'def not_in_the_same_phase(' in s)
  row['inputs_outputs'] = {'source_header':'def not_in_the_same_phase(module: ModuleNode, dependency: ModuleNode) -> bool','behavior':row['behavior']}
d['extends_previous_current_revision'] = 'API e84d348c: previous current observations remain recoverable by Git; immutable pinned pilot unchanged'
d['consumer_only_current_adaptation'] = {'ModuleGraph.from_database':'Public explicit-alias preparation entry point, distributed counterpart of reference cursor-bound extend/preparation; not another module installer','ModuleGraph.using':'Ephemeral source database alias, not a taxonomy or persistent field','ModuleNode.snapshot_attributes':'id,state,demo,installed_version,load_version,load_state now populated from retained catalogue rows'}
d['pending_specific_boundaries'] = ['Full loader and installed-version commit after successful installation','Imported module provenance/diagnostic exception','Schema/data/hooks/model registry/worker execution and acceptance','Cached-property reset lifecycle remains adapted to recomputing properties']
output.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
p=owner.INVENTORY/'outputs/ir-module-version-correspondence.json';versions=json.loads(p.read_text())
versions['previous_current_observation']='e84d348c: no separate installed-version field; now changed, historical record retained in Git'
versions['consumer_inventory']=owner.inventory.file_inventory(REPO/'src/addons/base/models/ir_module.py')
versions['consumer_sha256']=hashlib.sha256((REPO/'src/addons/base/models/ir_module.py').read_bytes()).hexdigest()
versions['evidence']=str(RUN.relative_to(REPO))
for row in versions['correspondence']:
 if row['reference']=='IrModuleModule.latest_version':
  row.update(consumer='IrModule.installed_version nullable, noneditable Char; preserves actual installed provenance separately from refreshed IrModule.version',verification='version-before-isolated.log3FAIL -> version-after.log3PASS; actual0088 migration forward/reverse on existing rows; snapshot16controls/12differential/twoDBisolation',acceptance='Bounded persistence and snapshot verified; installed-version finalization requires successful loader execution; official0382 pending and no merge')
versions['historical_compatibility']={'migration':'0088_module_installed_version','backfill':False,'legacy_rows':'Keep original version/state; installed_versionNULL because previous metadata is not evidence of an installation','taxonomy_migration':False,'reverse':'Real operation backwards preserves legacy metadata; dropping the new column naturally removes its newly stored values'}
versions['pending_installed_version_producer']='Only a successful future loader may finalize installed state and installed_version; no API accepting an arbitrary completion was added'
p.write_text(json.dumps(versions,indent=2,ensure_ascii=False)+'\n')
print('Updated current Consumer inventories and19qualified contracts; unchanged reference reused; other60named reference obligations remain pending')
