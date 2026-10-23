"""Extend the existing per-file authority with the existing inventory extractor."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
JOB = Path(__file__).resolve().parents[1]
BANK = ROOT/'scripts/workbench/odoo-orm-reference-inventory-20260910T181517'
spec = importlib.util.spec_from_file_location('owner_inventory', BANK/'inventory_reference_orm.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
reference = owner.TREE_ROOTS['odoo19c']/'odoo/modules/loading.py'
model_reference = owner.TREE_ROOTS['odoo19c']/'odoo/addons/base/models/ir_demo_failure.py'
p = BANK/'outputs/loading-contract-reconciliation.json'
d = json.loads(p.read_text())
assert hashlib.sha256(reference.read_bytes()).hexdigest() == d['reference_sha256']
symbol = next(r for r in owner.declared_symbols(reference) if r['name']=='load_demo')
record = {
 'reference_revision':d['reference_revision'], 'reference_symbol':'odoo/modules/loading.py::load_demo',
 'source_location':symbol['lineno'], 'owner':'odoo.modules.loading', 'symbol_kind':'function',
 'behavior':'Optional demo runs elevated within a savepoint; report failures without accepting the whole module lifecycle',
 'execution_flow':['No demo/demo_xml returns True','Elevated install_demo context; load_data demo within savepoint','Success returns True','On error rollback demo data and log complete traceback','Resolve optional todo and failure model; persist open todo and error only when both exist; return False'],
 'inputs_outputs':{'signature':symbol['signature'],'consumer':'load_demo(env, package, idref, mode); env.cr.alias binds selected Django database','precondition':'Explicit caller atomic transaction for work, matching domain routing alias, matching package catalogue identity before failure writes'},
 'side_effects':'Demo converter SQL/data, context activation/restoration, optional todo and complete error persistence; no own outer commit or installed/version finalization',
 'dependencies':['Existing Environment entered context manager','Django nested transaction.atomic','Existing tools.convert_file','Existing Django-label lookup for IrDemoFailure','Complete error storage and optional IrModelData todo reference','Caller registry/schema and company scope readiness'],
 'consumers':['Pinned load_module_graph','Pinned force_demo','Future Consumer module loader caller not integrated'],
 'installed_mechanism':['src/modules/loading.py::load_demo reuses load_data, Environment and Django atomic','IrDemoFailure.error now unbounded; base0089 protects narrowing reverse','Django-label fallback is a native equivalent, not a new canonical name or registry implementation'],
 'existing_adaptation':'Consumer env has no get and canonical demo model is not registered; existing Django-label lookup verified. Context requires with env(...) rather than merely creating a derived Environment. Caller owns transaction.',
 'verification':{'focused':'Nine initial red cases; definitive combined data/demo16PASS including added identity mismatch control','postgresql':'Error storage/application/reversal guard PASS; real-file SQL savepoint PASS; full migrated default stack verification running','negative':'Savepoint annulment exit1 leaves outer transaction aborted; length255 annulment exit1 detects lost content','evidence':str(JOB.relative_to(ROOT))},
 'equivalence':'Bounded mechanisms verified; complete N=1 full-stack outcome pending, native Odoo and productive N>1 not accepted',
 'limitations':'No XML/CSV, hooks, module schema/registry composition or installed-version producer acceptance. Existing automation alias and productive company provisioning blockers remain.',
 'integration':{'task':'TASK-API-0382','acceptance':'not_verified for full TASK','merge':False,'official_state_changes':False},
}
d['contract_records']=[r for r in d['contract_records'] if r['reference_symbol']!=record['reference_symbol']]+[record]
d['other_named_declarations_pending']=[r for r in d['other_named_declarations_pending'] if r['name']!='load_demo']
d['consumer_loading_inventory']=owner.file_inventory(ROOT/'src/modules/loading.py')
d['consumer_loading_sha256']=hashlib.sha256((ROOT/'src/modules/loading.py').read_bytes()).hexdigest()
d['scope']='Three reviewed source-flow contracts; four other named declarations remain pending. Counts are not contractual acceptance coverage.'
if (JOB/'outputs/verification-exits.json').exists():
    exits=json.loads((JOB/'outputs/verification-exits.json').read_text())
    record['verification']['postgresql']='Complete error storage/migration/guard and real-file savepoint PASS; full migrated N=1 stack exit'+str(exits['independent_demo_verifier_exit'])
    record['verification']['ci']='make exit'+str(exits['ci_make_exit'])+'; inherited first display_name error, later tests NOT_EVALUATED'
    record['equivalence']='N=1 bounded demo path verified with real migrated schema, files, converter, todo/XMLID/failure models and automation signals; full module lifecycle and N>1 not accepted'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
field_line=next(i+1 for i,line in enumerate(model_reference.read_text().splitlines()) if line.strip().startswith('error ='))
field_contract={
 'reference_revision':d['reference_revision'],'reference_symbol':'IrDemo_Failure.error','source_location':field_line,'owner':'odoo.addons.base.models.ir_demo_failure.IrDemo_Failure','symbol_kind':'field',
 'behavior':'Store complete demo exception text without declared size truncation','execution_flow':'load_demo captures traceback.format_exc and creates optional failure record after data rollback',
 'inputs_outputs':'Complete Unicode traceback in; identical stored string out', 'side_effects':'Failure record column write and base0089 column widening; old stored strings unchanged',
 'dependencies':['ir.module.module foreign key','Django field and PostgreSQL type','Existing textual conversion truncates only when model explicitly declares max_length'],
 'consumers':['load_demo reporting','IrDemoFailureWizard.failure_ids and failures_count'],
 'installed_mechanism':'IrDemoFailure.error Char without max_length; actual AlterField with explicit guard against narrowing while long data exists',
 'existing_adaptation':'Persistent Django model retains preexisting divergence from native TransientModel; no change to generic descriptor or taxonomy',
 'verification':'Real PG red storage mismatch -> green exact roundtrip; historical short row survives migration; long row prevents reverse before loss; negative length255 fails',
 'equivalence':'Complete error storage bounded contract verified; native Odoo not executed',
 'limitations':'Historical already-truncated contents cannot be reconstructed; no backfill guessed; wizard done() and transient cleanup not accepted',
 'integration':{'task':'TASK-API-0382','acceptance':'not_verified for full model/task','merge':False},
}
model_data={'reference_revision':d['reference_revision'],'reference_file':'odoo/addons/base/models/ir_demo_failure.py','reference_sha256':hashlib.sha256(model_reference.read_bytes()).hexdigest(),'reference_inventory':owner.file_inventory(model_reference),'reference_named_declarations':owner.declared_symbols(model_reference),'consumer_file':'src/addons/base/models/ir_demo_failure.py','consumer_sha256':hashlib.sha256((ROOT/'src/addons/base/models/ir_demo_failure.py').read_bytes()).hexdigest(),'consumer_inventory':owner.file_inventory(ROOT/'src/addons/base/models/ir_demo_failure.py'),'contract_records':[field_contract],'supplemental_field_scope':'Named-declaration extractor does not cover every field/constant; error attribute manually reviewed with exact source line. No new AST extractor.','other_obligations':'Wizard count property existing but not reverified; done/next integration and transient cleanup pending; canonical model registry naming unchanged.','evidence':str(JOB.relative_to(ROOT))}
(BANK/'outputs/demo-failure-correspondence.json').write_text(json.dumps(model_data,indent=2,ensure_ascii=False)+'\n')
print('Existing inventory reused; loading3 source-flow records,4 other declarations pending; exact error-field supplement recorded')
