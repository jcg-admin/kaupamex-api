# Module graph and company migration continuation

Objective: `completar-raiz-orm`; **objective_complete: false**.
This is the existing batch, not a new planner or acceptance authority.

## Revisions and native identities

- Odoo 19 Community reference: `abe4040ec1a45beee90fb694e4eae4453e46b389`.
- API graph/version publication: `3504014a9e016b6c99846fd26ad914d5465dc189`.
- API context correction local commit: `110c81827cdfb5e8d5d3b2f0698ffd4a3a7c8ceb`.
- Thyrox inspected: `9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f`.
- Native session: `168b0fdf-bfe4-590b-b6c0-b6be124c124a`.
  TaskGet local737 = TASK-API-0382; local738 = TASK-API-0383;
  owner `codex-module-lifecycle`, both pending. See `outputs/task-*.json`.
- PR109 and PR154 remain open, unmerged; publication snapshots are observations,
  not integration or acceptance. See `outputs/recovery-publication-state.json`.

## Existing Provider interfaces actually used

`THYROX_ROOT=/workspace/thyrox bun run probes/native_task_snapshot.ts` invokes
`taskTools({dbPath:storePath(),sessionId}).TaskGet.run` read-only. The script
checks the declared Provider revision and the two owned TASKs. It does not
restore a store or transition TASK status.

`session.task_continuation.plan_items_from_rows`, `claims_ledger_rows` and
`node_frontier` are used from the Provider interpreter with
`PYTHONPATH=/workspace/thyrox/src`. `outputs/selection-*.json` preserve bounded
inputs, decisions and limitations. These inputs are engineering subunits of
existing native tasks, not newly minted TASKs or a complete goal plan.
The whole-goal candidate source and managed-model dispatch remain unqualified.
A scoped empty selection must never be interpreted as global exhaustion.

`claimsCommand` from `src/packages/cli/src/commands/claims.ts` reads/reserves/
releases through the existing native append-only ledger. No manual ledger or
TaskStore edits. `session.job_runs` and `workbench.manifest` own job/manifest
scaffolding. No duplicate coordinator, scheduler, selector or evidence store.
Codex performs host engineering; no local-model inference is claimed.

## Verification boundaries

- Stored installed version and catalogue: three controls PASS; historical
  AddField application/reversal PASS, old version/state retained and installed
  provenance NULL. No successful module-loader producer has been verified.
- Database graph: initial16 FAIL ->16 PASS; four extra preparation boundaries
  bring the maintained set to20 PASS. Pinned-source differential12 PASS;
  two physical databases show independent snapshots. The memory-only mutation
  ran on the initial16 and produced11 PASS/5 FAIL, expected exit1.
- Existing inventory/contract30 PASS and static graph12 PASS are separate,
  potentially overlapping observations, not a contractual denominator.
- Provisioner context:9 FAIL/2 PASS ->11 PASS; memory-only annulment8 FAIL/3 PASS,
  expected exit1. Caller context restores after success/failure, including007.
- First global CI:77 PASS/1 SKIP/1 ERROR,512.57s, make exit2.
- After context correction:77 PASS/1 SKIP/1 ERROR,542.65s, make exit2.
  Both stop at inherited ProductProduct.display_name setup failure;
  later tests/stages NOT_EVALUATED, not proof of no further regressions.
- Full default schema:379 applied migrations,107 local res_users FKs.
  First company attempt failed at base0005 without target company context.
  Context correction reaches a different failure: django_content_type absent.
  Independent verifier exit1; combined wrapper preserved CI exit2.
- Bounded contenttypes diagnostic:exit0 confirms migration plan0001/0002 is
  recorded applied on the correct physical company DB but the table is absent
  because allow_migrate rejects contenttypes. base0060 declares the dependency
  and attempts resource_ref_content_type FK. This is a reproduced failure
  classification, not successful provisioning. Resources removed.
  The first diagnostic log has an inappropriate default PASS label: default
  was not migrated in this mode; JSON records that omission. Probe corrected
  to emit NOT_EVALUATED on this branch; original log is retained unchanged.
- In-memory local-contenttypes full-company experiment: see corresponding log
  and JSON. Experimental override is not a production policy correction or
  TASK acceptance. Sessions routing is not changed.

## Reproduce using owned PostgreSQL resources

Use the existing `orm-bootstrap-compute-20261021T210528/probes/qa_context.py`.
Set ORM_QA_CONTAINER, ORM_QA_HOST and ORM_QA_BRIDGE for the existing container;
run with `uv run --frozen`, not SQLite or shared QA recreation. The wrapper
creates a random role/database, private HBA marker and removes them in finally.
Company probes grant CREATEDB only to that random role, create a random
company database and clean it plus its HBA marker in finally. Do not run the
legacy fixture on fixed company_8801/8802 databases without ownership checks.

`probes/verify_full_company_migrations.py --diagnose-contenttypes` is a bounded
MigrationExecutor observation without full default migration.
`--company-only --probe-local-contenttypes` is an explicitly experimental
in-memory routing hypothesis, with sessions unchanged. `--reuse-default` is
valid only inside the same owned CI wrapper after default migrations exist.
The ordinary full verifier does not apply experimental overrides.

Capture terminal output with pipefail and tee; logs, JUnit and JSON preserve
actual exits. `make ci-verify` must use CI_DATABASE_DISPOSABLE equal to the
random owned DB name. Do not rerun full CI for documentation-only changes.

The old /tmp/orm_batch_env.py helper has a persistent recovery copy in
`orm-module-lifecycle-20261022T023817/probes/recovery/orm_batch_env.py.source.txt`.
It supplies import-only settings for hooks, not a runnable shared-QA fixture.
Do not replay historical admission scripts that perform TaskUpdate merely to
recover settings or evidence. No .env, identity, hooks or baseline changes.

## Contractual continuity

Reuse the existing reference inventory outputs:
module-graph-contract-reconciliation.json, ir-module-version-correspondence.json
and loading-contract-reconciliation.json. Graph19 named occurrences retain
14 dimensions;60 other IrModule declarations and five other loading functions
remain pending. Inventory/mapping/verification/acceptance are distinct.
The installed-version producer depends on real schema/data/hooks execution;
request states and Registry primitives alone do not discharge that contract.
Existing TASK/Implementation AS IS remain the authorities; update only affected
observations. No new TASK, taxonomy migration, whole-repository inventory,
merge or claim of whole ORM completion belongs to this batch.

## Recovered continuation observations

HR historical migration fix local8bf4369f: active-company PG control RED1,
GREEN0, memory-only annulment1 expected. Initial no-company control did not
exercise the callable and is retained as a control limitation. The next
company-only experimental replay exits1 at website_sale._default_salesteam_id
calling IrModelData.ref with implicit default alias; ir_model_data is absent
in the deliberately empty central DB. This does not qualify productive
company provisioning. No router/contenttypes policy change was committed.

The reduced metadata/session control exits1 in automation pre_save before
its remaining assertions: explicit alias is lost in _capture_old_values.
Cache/session checks after that error are NOT_EVALUATED. Native historical
TASK-GEN-0073 completed/owner null is a related authority, not admission for
new signal edits. No automatic TASK or ownership transfer was performed.

Native0382 selected manifest-data stage independently; first maintained
control collection exits2 because modules.loading is absent. This stage
reuses tools.convert_file and cannot finalize installed state or version.
The production implementation is pending while active validation completes.

## Final verification checkpoint

Source commits110c8182,8bf4369f and2cc7758d are published on the existing
feature branch. After-HR CI:77PASS/1SKIP/1ERROR461.12s make2. After-data
CI:77PASS/1SKIP/1ERROR497.81s make2. Both stop at the inherited display_name
setup error; later tests/stages NOT_EVALUATED. No verifier is still running.
Final native PostgreSQL observation: zero owned orm_bootstrap databases and
zero owned roles. Each company probe also removed its second database.

Manifest-data implementation is now src/modules/loading.py::load_data,
not merely a proposed stage: six maintained controls PASS, five pinned
function comparisons PASS, actual PG SQL duplicate/rollback PASS. Definitive
negative1FAIL/5PASS exit1 expected; initial within-list mutant did not exercise
the cross-key duplicate and is retained as a limitation. File-open was an
isolated BytesIO collaborator: addon path/XML/CSV/full-loader acceptance is
not inferred. This stage does not write installed state/version or commit.

Remaining demo execution needs verified alias-local optional model resolution,
existing Environment context activation/savepoint semantics and error
persistence. A class-only empty MODELS_BY_NAME mapping is not evidence of
absence in an initialized Registry. Environment.get is absent; demo error
storage is limited to255. These are qualification inputs, not permission to
truncate errors, invent a new registry or change another owner's code.

The automation alias problem is reproduced historical debt already named in
previous-as-is-owned-frontier.json, not a newly minted finding. Keep its
owner/admission unresolved until reconciled; completed TASK-GEN-0073 with NULL
owner does not authorize taking new work. Production contenttypes placement
is unchanged. All whole TASKs and the persistent objective remain unaccepted.

Native continuation selected demo-contract qualification after data publication.
probes/qualify_demo_runtime.py actually constructs Registry(default) on owned
PostgreSQL: canonical ir.demo_failure lookup fails, Django label resolves;
explicit elevated context activates/restores and SQL rollback passes. Exit0
is a bounded dependency observation. Complete failure persistence/long error/
optional todo/company-signal verification remains not_verified; the demo
execution dependency is not marked accepted or dispatched. The frontier is
not a proof of global exhaustion and the initiative remains incomplete.
