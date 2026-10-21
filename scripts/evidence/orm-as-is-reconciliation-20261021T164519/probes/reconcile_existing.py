"""Cruce analítico Consumer sobre autoridades ya existentes; sin estados oficiales."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip())
run=Path(__file__).resolve().parents[1]; out=run/'outputs'
base=root/'scripts/evidence'
coverage_path=base/'orm-contract-plan-testorm-20261020T202537/outputs/functional-contract-coverage.json'
coverage=json.loads(coverage_path.read_text())
tasks=json.loads((out/'task-as-is.json').read_text())
notes={
 'record_identity_singleton':('partial historical verification','BaseModel id/ensure_one evidence reused. 0402 constructor/from_db/save already install triple; no reimplementation. Singleton does not prove all recordset access.'),
 'exists_recordset_semantics':('not_verified','Empty branch has existing test. Persisted/new/id0 path still not verified; native QuerySet.exists bool is not equivalent.'),
 'cache_value_and_miss':('partial historical verification','Existing Cache.get/set/miss adaptation and historical tests; completed GEN0575 is not acceptance of all cache contracts.'),
 'cache_across_user_environments':('not_verified','Exact two-user set/overwrite/remove flow still not demonstrated; transaction ownership tests are narrower.'),
 'selective_invalidation':('partial historical verification','Existing Field/cache/Transaction removal tests and prior evidence; broader composed/context path not verified.'),
 'row_rule_access':('not_verified','AccessQuerySet and existing rule tests present; requires prepared security fixtures. Missing res_users blocks global setup, no independent security acceptance.'),
 'cursor_transaction_lifecycle':('partial historical verification','Prior PostgreSQL transaction probe reused; ownership/replica/concurrency not accepted globally.'),
 'cursor_replica_selection':('confirmed divergence / protocol evidence','Prior six branch scenarios retained; cooldown/thread/ProgrammingError differences, no real replica qualification; no atomic TASK identity reconciled.'),
 'inverse_dependency_navigation':('partial historical verification','Registry inverse/trigger mechanisms and prior22cases retained; API0424 warns of searchable related chain, not automatically a bug.'),
 'domain_any_rights_optimization':('bounded historical verification','Prior eight predicate comparisons/negative controls reused; not full CRUD/domain/security conformance.'),
 'invalidate_all_flush_before_invalidate':('confirmed defect, identity blocked','Existing exact-body control shows Consumer ignores flush. Search still finds no exact TASK; do not implement under broad completed Cache task.'),
 'flush_recompute_fixpoint':('partial historical verification','Prior six orchestration scenarios and two mutants reused. New missing-row cleanup does not accept entire fixpoint or alter empty-dirty representation.'),
 'relational_field_reconstruction':('bounded adapted equivalence','Published0419 correction preserved. Prior8cases + new5PostgreSQL cases verify forward/reverse/query,PROTECT/CASCADE,FK integrity,rollback. Whole Odoo relational semantics not accepted.'),
 'recompute_dependent_record_discovery':('partial, new bounded correction verified','GEN0559 missing persisted IDs after queryset filtering:7PASS, baseline3PASS/4FAIL. Native group cleanup, virtual/subset/compute-error preservation. No batch0558, relation-discovery0424 or stale-row mid-compute race acceptance.'),
 'translated_record_storage_query':('confirmed divergence, migration blocked','Prior varchar/jsonb evidence reused. GEN0060->GEN0062 raw dependency retained. API0283 metadata/PR110 is not storage acceptance; no migration authorized.'),
 'json_value_isolation_roundtrip':('bounded adapted equivalence','0420 literal nested isolation, serialization and real JSONB persistence evidence reused; current focused regression passes7JSONcases. Global CI setup and timezone drift remain acceptance blockers.'),
 'recordset_sort_order':('implemented, full conformance not_verified','API0400 completed and _sorted_order_to_function present; selected historical tests do not establish full sort semantics/acceptance.')}
records=[]
for entry in coverage['records']:
 name=entry['descriptor']; status,note=notes.get(name,('not_verified','Existing reference characterization and candidate implementation retained; no new execution or admission for this obligation.'))
 records.append({'descriptor':name,'source':str(coverage_path.relative_to(root))+'#records/'+name,
 'diagnosis':status,'observation':note,'reference_revision':coverage['revision'],
 'existing_tasks':entry['contract'].get('existing_task_relationships'),'integration':'not_verified; no merge authorized'})
# Mantener cada caracterización completa navegable sin duplicar sus14elementos.
groups=[{'source_group':r['source_group'],'source':str(coverage_path.relative_to(root))+'#full_module_characterizations/'+r['source_group'],
 'diagnosis':'historical source analysis retained; current whole-group Consumer conformance not_verified',
 'delta_limit':'0419/0420/GEN0559 are bounded subcontracts, not acceptance of an entire group'} for r in coverage['full_module_characterizations']]
commit_notes={
 'TASK-API-0402':('pending_with_existing_implementation','src/orm/models.py BaseModel.__init__/from_db/_install_singleton_triple/save','Existing construction adaptation; preserve; no full TASK acceptance inferred.'),
 'TASK-API-0419':('integration_pending','src/orm/fields.py; tests/unit/orm/test_relational_field_reconstruction.py; tests/unit/orm/test_relational_reconstruction_persistence.py','6c11ddde existing correction + five new PostgreSQL verification cases; no reimplementation.'),
 'TASK-API-0420':('integration_pending','src/orm/fields_misc.py; tests/unit/orm/test_json_defaults.py','8aca3900 preserved; valid prior JSONB/default/migration controls. No global CI acceptance.'),
 'TASK-GEN-0559':('in_progress_with_verified_progress','src/orm/models.py::_recompute_field; tests/unit/orm/test_missing_recompute.py','Bounded missing-row cleanup implemented/verified, official pending unchanged. Mid-compute deletion retry remains not_verified.'),
 'TASK-API-0399':('pending_without_implementation for exact missing fetch path','src/orm/models.py::mapped','Code still raises explicit NotImplementedError for large mapped batches; broad fetch plan deferred.'),
 'TASK-API-0401':('blocked_by_dependency / architectural decision','src/orm/models.py::_read_field; src/orm/fields.py descriptors','Plain multi-record access decision/cost requires authority reconciliation; not generic descriptor rewrite.'),
 'TASK-API-0216':('blocked_by_contract_reconciliation','src/orm/fields.py::__all__; src/addons/base/models/ir_model.py','Historical classes-only criterion conflicts with intentional factories. Do not implement an invalid guard.'),
 'TASK-API-0417':('in_progress_with_verified_progress, residual not accepted','src/orm/fields_nonstored.py; src/orm/field_source.py; tests/unit/orm/test_declared_source_vocabulary.py','20dc122b central derivation exists; three inherited failures retained. No arbitrary test weakening.'),
 'TASK-API-0418':('blocked_by_scope_reconciliation','src/orm/fields_nonstored.py::NonStored','General adoption residual; not a prerequisite for measured0419 mixin path.'),
 'TASK-API-0424':('verification_required_before_defect_claim','src/orm/models.py modified/_recompute_field; src/orm/registry.py triggers','Related-chain searchability warning may be reference-faithful. New0559 cleanup is not this contract.'),
 'TASK-GEN-0558':('pending, existing per-row adaptation','src/orm/fields.py::recompute/_invoke_compute_method','QuerySet batch/prefetch unit distinct; not prerequisite for removing missing persisted IDs after query.'),
 'TASK-THYROX-1072':('claimed_without_observable_progress','Thyrox src/task/task_source.py::records_from_store','Foreign vm-r claim retained; source still hardcodes blockedBy=[]. Cross-VM liveness/progress not verified.'),
 'TASK-GEN-0060':('blocked_by_persistence_and_migration_authority','src/orm/fields_textual.py','Known storage divergence; no migration authorization.'),
 'TASK-GEN-0062':('blocked_by_dependency','native same-session dependency333 resolves GEN0060, see raw rows/previous dependency evidence','Depends on GEN0060 despite lossy projection; not eligible from empty edges.'),
 'TASK-GEN-0575':('completed_but_unverified for whole contract','src/orm/environments.py::Cache','Cache implementation and focused history exist; no global acceptance of28methods.'),
 'TASK-GEN-0578':('completed_but_unverified for whole contract','src/orm/fields.py::_filter_not_equal/_update_inverse','Existing adaptation; related local verification is not whole-contract acceptance.'),
 'TASK-API-0400':('completed_but_unverified for whole contract','src/orm/models.py::_sorted_order_to_function','Implementation present; reuse existing tests, no reimplementation.'),
 'TASK-API-0421':('completed_but_unverified for whole contract','src/orm/models.py::BaseModel.create','Existing dict/list adaptation and historical content evidence; not accepted merely by completed.'),
 'TASK-API-0412':('completed_but_unverified for whole contract','src/orm/fields.py::determine_inverse; src/orm/models.py::RecordLoaderMixin.save','Inverse dispatch present; transaction atomicity GEN0507 remains distinct.'),
 'TASK-API-0427':('blocked diagnosis, no root cause attribution','Existing lock investigation and current CI res_users log','Historical lock symptom is not proof of current missing-table cause; no speculative CI fix.')}
views=[]
for row in sorted(tasks['native_rows'],key=lambda r:r['citation_id']):
 cite=row['citation_id'];diag,code,note=commit_notes.get(cite,('not_verified; retain official '+row['status'],'Existing scope authority and task-as-is.json native row','Scope or evidence insufficient for admission; no absence or correctness inferred from status.'))
 views.append({'citation':cite,'identity':[row['session_id'],row['task_id']],'official_status':row['status'],'official_owner':row['owner'],
 'functional_owner':'API for ORM contract; historical GEN layer does not change ownership automatically' if not cite.startswith('TASK-THYROX') else 'Thyrox',
 'claims':row['active_claims'],'dependencies_raw':row['blocked_by_json'],'diagnosis':diag,'implementation_navigation':code,'observation':note,
 'verification':'specific evidence referenced above; otherwise not_verified','publication':'API109 published baseline35501644; new unit publication recorded in PR after commit',
 'acceptance':'not_verified for whole TASK','integration':'not merged','next_action':'Use scoped contract note; unknown scope/ownership/dependencies requires reconciliation, no automatic dispatch'})
result={'scope':'Analytical view over existing33descriptors/66source characterizations plus native55scoped task identities; not a new population/store or global denominator',
 'reference_revision':coverage['revision'],'implementation_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'working_source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['src/orm/models.py','tests/unit/orm/test_missing_recompute.py','tests/unit/orm/test_relational_reconstruction_persistence.py']},
 'contracts':records,'source_groups':groups,'task_view':views,
 'unresolved_historical_refs':[r for r in tasks['historical_scope_refs'] if not r['citation']],
 'no_reimplementation':['0420 Json deepcopy default','0419 relational constructor capture','0402 singleton triple injection','0400 sorted helper','Cache/grouping/removal and native Thyrox mechanisms'],
 'unmapped_implementation_limit':'No exhaustive code-to-TASK correspondence claimed. Prior unmatched symbols are not automatic defects/TASK.',
 'coverage_limit':'Complete current functional verification of all applicable obligations remains open; untouched mechanisms retain historical evidence with limitations, not new PASS.'}
(out/'reconciliation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# TASK AS IS / Implementation AS IS / Contractual Reconciliation','',result['scope'],'',
'All official statuses unchanged. Missing description/owner/dependency is not readiness. Native task-source graph currently loses edges; no executable frontier is fabricated. All integration/whole TASK acceptance remains pending.','',
'## TASK AS IS','', '| TASK | Official status | Diagnosis | Observed code/evidence or gap |','|---|---|---|---|']
for r in views:lines.append('| '+ ' | '.join([r['citation'],r['official_status'],r['diagnosis'],r['observation']]).replace('\n',' ')+' |')
lines+=['','## Implementation AS IS and reconciliation','', '| Existing contract | Diagnosis | Evidence and limits |','|---|---|---|']
for r in records:lines.append('| '+' | '.join([r['descriptor'],r['diagnosis'],r['observation']])+' |')
lines+=['','All66source groups remain linked individually in reconciliation.json to original14-element records. None is silently omitted or accepted from file counts. Eight legacy board refs have no mapping in the checked original session; kept unresolved, no guessed identities.','',
'## Continuation','',
'0420: global migrations timezone debt and shared CI setup1120 block acceptance, not reimplementation.0419: new FK persistence closes a bounded verification gap; M2M/O2O persistence, race/concurrency and whole ORM integration remain open. GEN0559: scope-admitted query-missing cleanup now7PASS vs4baselinefail; stale loaded row deleted during compute and native MissingError retry not accepted.0558 batching remains separate. Invalidate_all flush defect has no exact reconciled TASK; do not silently use completed0575. Translation needs storage/migration authority. No remote/local-model inference claimed.','',
'Recover this run through native latest_run(jobs_dir(consumer_root()), "orm-as-is-reconciliation") and its existing manifest. Read source authorities by linked relative paths and exact pinned revision, not transcript/scratch. Existing BABOK portable handoff in Docs babok-operational-continuation-20261021T153929 remains applicable; Podman still absent.','']
(out/'reconciliation.md').write_text('\n'.join(lines))
print('Reconciled',len(records),'existing descriptors,',len(groups),'existing source groups,',len(views),'native task identities; no states changed')
