"""Dependencia de finalización: usa inventario y procedencia existentes, no otro extractor."""
import hashlib
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RUN = Path(__file__).resolve().parents[1]
INVENTORY = REPO/'scripts/workbench/odoo-orm-reference-inventory-20260910T181517'
spec = importlib.util.spec_from_file_location('owner_inventory',INVENTORY/'inventory_reference_orm.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
source = owner.TREE_ROOTS['odoo19c']/'odoo/modules/loading.py'
prior = json.loads((REPO/'scripts/evidence/orm-as-is-substantive-20261021T194156/outputs/res-users-bootstrap-comparison.json').read_text())
record = next(r for r in prior['source_evidence'] if r['path']=='odoo/modules/loading.py')
assert hashlib.sha256(source.read_bytes()).hexdigest()==record['sha256']
# El archivo ya tenía evidencia parcial de flujo, no inventario por archivo.
structural = owner.file_inventory(source)
records = owner.declared_symbols(source)
selected = next(r for r in records if r['kind']=='function' and r['name']=='load_module_graph')
contract={'reference_revision':'abe4040ec1a45beee90fb694e4eae4453e46b389','reference_symbol':'odoo/modules/loading.py::load_module_graph','source_location':selected['lineno'],'owner':'odoo.modules.loading','symbol_kind':selected['kind'],'behavior':'Load/register models; perform per-module update lifecycle; finalize installed state/version after domain operations, before at_install tests','execution_flow':['Determine install/upgrade/reinit only when update_module enabled','Pre-migration, imports and pre-init hook','Registry.load, inheritance descendants and incremental model setup/schema initialization','Module checks and data/demo loading','Persist demo, post-migrations and translations','Post-init hook for installation or view validation for upgrade','Append updated_modules; adapt manifest version; write state installed and stored latest_version','Update package.state, flush and commit','Optional at_install tests and report; runtime installation marker is not TASK/PR acceptance'],'inputs_outputs':{'signature':selected['signature'],'source_header':'\n'.join(source.read_text().splitlines()[114:122]),'returns':'None; side effects on registry, database and optional test report'},'side_effects':'Imports/models, DDL/data/hooks, module state/version writes, flush/commit and test report; no equivalent guaranteed by mere migrate success','dependencies':['Native Odoo Cursor/Environment/Registry for native reference execution','MigrationManager and module data/demo/hooks consumers','Consumer selected-alias graph and stored installed provenance now prepared, not an execution pipeline'],'consumers':['load_modules caller','Registry construction/update lifecycle','MigrationManager reads package.load_version/load_state'],'installed_mechanism':['Consumer ModuleGraph.from_database provides readonly graph','IrModule.installed_version stores counterpart of reference latest_version but no successful loader producer exists','service.db.provision_company_database applies Django project migrations, separately verified under0383','Registry.load/init_models have partial cache/reflection behavior; current init_models does not emit per-package model DDL'],'existing_adaptation':'One distributed contract across graph/catalogue/registry/backend. Source names or module __init__ docstring are not evidence of functional equivalence. No new version finalization API without execution proof.','verification':{'source':'Pinned source body and historical source hash matched; actual Consumer service/registry bodies reviewed','schema':'Full default/company migration probe is independent prerequisite, not loader acceptance','positive_negative':'Snapshot/migration/alias tests apply only to their bounded contracts; native load_module_graph execution NOT_EVALUATED','missing_fixtures':'Native Odoo runtime/cursor and complete Consumer loader integration fixture not available in this unit'},'equivalence':'not_verified for full loader; partial graph/catalogue/schema mechanisms identified concretely','limitations':'No installation success inferred from CI, migration count, class existence or copied manifest version. Native at_install tests occur after installed write/commit, so runtime installed and independent task acceptance are distinct.','integration':{'task':'TASK-API-0382','related_task':'TASK-API-0383 for whole-database schema prerequisite only','acceptance':'not_verified','merge':False}}
d={'extends':'Existing res-users-bootstrap-comparison.json loading source flow/hash; existing ModuleGraph and version ledgers','reference_file':'odoo/modules/loading.py','reference_revision':contract['reference_revision'],'reference_sha256':record['sha256'],'reference_inventory':structural,'contract_records':[contract],'other_named_declarations_pending':[dict(r,qualified_symbol=(r['owner']+'.' if r.get('owner') else '')+r['name'],acceptance='not_verified',task_resolution='not_verified') for r in records if r is not selected],'extraction_limits':'Existing top-level/direct-method extractor; imports/constants/conditional/nested/dynamic source require progressive supplemental review. No exhaustive structural or semantic claim.','consumer_dependencies':['src/modules/module_graph.py','src/addons/base/models/ir_module.py','src/service/db.py','src/orm/registry.py'],'scope':'Only the installed-version producer path is reviewed semantically; no automatic seven-file-count contractual denominator or new TASKs','evidence':str(RUN.relative_to(REPO))}
d['consumer_service_inventory'] = owner.file_inventory(REPO/'src/service/db.py')
d['consumer_service_sha256'] = hashlib.sha256((REPO/'src/service/db.py').read_bytes()).hexdigest()
d['company_migration_context'] = {
 'task':'TASK-API-0383', 'source':'src/service/db.py::provision_company_database',
 'caller':'src/addons/base/management/commands/company_create.py',
 'precondition':'Management enabled; declared company_<N>_db target; alias installed before migrate',
 'mechanism':'Existing company_scope around migrate; implicit historical-model routing follows target and previous context is restored',
 'verification':'provision-context-before.junit.xml9FAIL/2PASS -> provision-context-after.junit.xml11PASS; memory-only context annulment8FAIL/3PASS expected',
 'observed_before':'Full default migration379applied and107FKs to local res_users; company failed in base0005 implicit update without scope',
 'replay':'Combined CI after context failed at inherited display_name; company failed at missing contenttypes. HR historical default subsequently fixed; later experimental company-only replay fails in website_sale default using central IrModelData.ref.',
 'history':'Router policy and base migration history unchanged; measured HR migration now separates nullable DDL from preserved runtime default. Leading-zero company aliases preserved.',
 'acceptance':'not_verified; full company migration, legacy skipped fixtures, CI/review/integration remain separate obligations',
}
p=INVENTORY/'outputs/loading-contract-reconciliation.json'
# Preserve additional manually reconciled contracts in the existing ledger.
# Source/hash checks prevent silently carrying annotations to another reference.
if p.exists():
    previous = json.loads(p.read_text())
    assert previous['reference_revision'] == d['reference_revision']
    assert previous['reference_sha256'] == d['reference_sha256']
    additional = [r for r in previous['contract_records']
                  if r['reference_symbol'] != contract['reference_symbol']]
    declared = {r['name']: r for r in records}
    for reviewed in additional:
        name = reviewed['reference_symbol'].split('::')[-1]
        assert name in declared and reviewed['source_location'] == declared[name]['lineno']
    d['contract_records'].extend(additional)
    reviewed_names = {r['reference_symbol'].split('::')[-1] for r in d['contract_records']}
    d['other_named_declarations_pending'] = [r for r in d['other_named_declarations_pending']
                                           if r['name'] not in reviewed_names]
    for key in ('consumer_loading_inventory', 'consumer_loading_sha256'):
        if key in previous:
            d[key] = previous[key]
    d['scope'] = previous.get('scope', d['scope'])
p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
print('Reused loading source provenance;',len(records),'named declarations;',len(d['contract_records']),'reviewed contracts;',len(d['other_named_declarations_pending']),'others pending')
