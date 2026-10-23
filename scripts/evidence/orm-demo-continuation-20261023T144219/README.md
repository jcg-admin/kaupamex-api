# Current-instruction validation and demo continuation

Objective `completar-raiz-orm`: **incomplete**. Existing TASK-API-0382, native
session168b0fdf-bfe4-590b-b6c0-b6be124c124a/local737, owner
codex-module-lifecycle. TASK-API-0383 remains pending. No TaskUpdate, new TASK,
model inference, merge, protection change or taxonomy migration was performed.

`outputs/instruction-validation.json` reviews clauses0..56 of the current
attached continuation document, preserving its SHA256 and baseline revision.
Initial assessment:36 procedural clauses verified,18 partial,3 acceptance
criteria not satisfied. These counts are document clauses, not TASK counts,
software defects or percentages of accepted ORM contracts. Current actions
are appended separately; the whole instruction is not declared fulfilled.

## Implemented and verified

- c6d88a44 removes the model-specific255-character error limit, preserving
  the generic Char descriptor. Native conversion had silently clipped the
  error, as shown by actual PostgreSQL roundtrip failure. Base0089 widens
  the column and prevents narrowing reversal while long errors exist.
  Two maintained PG controls verify exact Unicode storage, historical short
  data, guarded reverse and safe reverse after removing only the fixture row.
  Already-truncated historical content cannot be reconstructed or backfilled.
- d861c057 adds load_demo using existing Environment, load_data/convert_file,
  Django atomic and Django-label resolution. Caller transaction and correct
  alias/catalogue identity are required. Optional errors are recorded after
  demo rollback; reporting errors propagate. State/version are not finalized.
-16 focused data/demo controls PASS. Nine initial demo controls failed before
  implementation; the identity test was added during implementation.
- Actual files/native converter/PostgreSQL savepoint PASS; optional reporter
  absent in that bounded fixture. Memory-only savepoint annulment exits1
  with an aborted outer transaction, as expected.
- Memory-only restoration of the255 limit exits1 on lost contents, expected.
- Full migrated N=1 verifier PASS: actual configuration step, XMLID, failure
  model and automation signals, actual addon-root files and SQL converter.
  Failed data rolls back; success remains owned by the caller transaction;
  context restores and module state/version stay unchanged. Complete19117
  character synthetic error is saved in outputs/demo-original-error.txt.

## CI and limitations

make ci-verify exits2:77PASS/1SKIP/1ERROR519.64s, first inherited
ProductProduct.display_name error. Later tests/stages NOT_EVALUATED.
The independent full-stack verifier exits0; the wrapper retains CI exit2.
See outputs/verification-exits.json, ci.junit.xml and ci-and-demo.log.
No full CI repetition was made for local-identifier-only renaming.

The first demo commit was rejected by the normal identifier gate for local
`todo` names. Variables/test names were changed to configuration_step;
models and XMLIDs were preserved.16 controls passed again and normal hooks
passed. No --no-verify, gate/baseline edit or policy relaxation was used.

Productive N>1 migrations still have unchanged contenttypes/metadata alias
and historical default blockers from the previous batch. The existing
unowned completed automation task does not admit new signal edits. Effective
per-base model composition, hooks, whole-loader/version/state finalization,
other loading declarations, review and integration remain unaccepted.
The native scoped per-company frontier is not proof of global exhaustion.

## Reproduction and Provider provenance

Use existing qa_context.py in
orm-bootstrap-compute-20261021T210528/probes, uv run --frozen, existing
kaupamex-postgres-cloud and ORM_QA_HOST/ORM_QA_BRIDGE settings. It creates a
random own database/role/HBA marker and cleans them in finally; no shared QA.
Only that own role is granted CREATEDB for make ci-verify. The combined run
reuses the migrated CI database for verify_demo_full_stack.py after saving
JUnit, preserving both exit codes. Do not run the full-stack probe against
an unmigrated database or reuse a removed CI database.

probes/verify_error_storage.py runs maintained storage/migration controls;
--annul-length --storage-only is an expected-negative process.
probes/verify_demo_savepoint.py uses real addon-root files and PG;
--annul-savepoint is expected-negative. Temporary directories are created
atomically under the existing addons root and removed by their own context.

Provider9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f:
TaskGet uses taskTools({dbPath:storePath(),sessionId}) through the existing
native export probe; actual argv/cwd/interface/result are in task-*.json.
The first current reads were exported by the previous probe; those current
observations were copied here before the published historical exports were
restored exactly. Subsequent native reads use this job's own copied probe.
claimsCommand is used for all reservations/releases. node_frontier with full
claims ledger selects existing owned subunits; no alternative selector or
TaskStore exists here. Native jobs_dir/scaffold_run/declare_workbench/settle
own this job. No managed local-model dispatch is claimed.

Reconciliation uses the existing reference_roots and inventory extractor at
pinned Odoo19Community abe4040ec1a45beee90fb694e4eae4453e46b389. It updates
loading-contract-reconciliation.json and demo-failure-correspondence.json,
and only current0382 observations in the existing62-task AS IS population.
No global inventory, plan, AST extractor or finding number was recreated.
