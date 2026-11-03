# Contract continuation: replica flow, flush and dependency preservation

Analysis only. Consumer90cc7b78ecf727c352c5edd602b0fdf199198069,
Docs34ff351410c323e2844c2e2acdaf0791fba0fe1b, Provider
9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f. Reference Odoo19Community
abe4040ec1a45beee90fb694e4eae4453e46b389. No product fixes, TASK state
changes, taxonomy migration or PR merge. Existing evidence packages reused.

## New controls and scope

Cursor: six scenarios, nine calls per side, two in-memory mutants. Actual bodies
extracted via existing extract_both_sides.bodies. Shared four positive branches;
retry cooldown, thread mode and ProgrammingError handling differ. Reference
cooldown1200seconds is simulated by deterministic clock, not a live wait.
First attempt exit1 psycopg2 absent is preserved. Final protocol uses explicit
reference exception hierarchy and actual Django exceptions; exit0 demonstrates
body branches, not psycopg2 runtime, real replica/readonly/SQL/pool/concurrency.

Flush: six scenarios, five matching orchestration observations and one declared
empty-dirty-entry representation difference. Two mutants omit recompute or
ceiling warning and are rejected. Explicit in-memory OrderedSet/model resolver
bridge: no claims about native implementations, PostgreSQL writes or cleanup.
No earlier invalidate_all or transaction probe was repeated.

## Reproduction

Use API checkout, uv frozen, ODOO_TOOLS set to a verified checkout/extraction of
the exact reference revision above; scripts/reference_roots.py owns resolution.
THYROX_CONSUMER optionally selects API root; probes otherwise walk from __file__.

UV_CACHE_DIR=<cache> ODOO_TOOLS=<verified-root> uv run --frozen python
<run>/outputs/probe_cursor_fallback.py

Same command with outputs/probe_flush_fixpoint.py. Reports record actual Python,
Django and psycopg versions and hashes of both sources, bodies and extractor.
No required import lives in scratch: both portable probes are versioned here.
The reference API retrieval commands, Git blobs and SHA256 of the two newly
materialized tests are in reference-tests-provenance.json. Rebuild the partial
reference from those revision-pinned contents paths; it is not a full runtime.

Existing reference_flow CLI executed for invalidate_all/flush_all/
invalidate_field_data with --root odoo/orm --root odoo/addons/base/tests:
25files universe,4parsed. Existing same core on Consumer src/orm+tests/unit/orm:
131files,7parsed. Logs retained; no global functional denominator inferred.
Reference tests characterize cache sharing/selective invalidation and CRUD/
search/security cases. Files read, not executed; no upstream CI success claim.

## Provider mechanisms actually used

Native session.job_runs jobs_dir(start),scaffold_run,settle;
workbench.manifest.declare_workbench; TypeScript checkWorkbench;
claimsCommand claim/release owner codex-contract-continuation. Provider version
above, no synthetic functional TASK attached. Uses native evidence anatomy.

Readonly agent_store/task_ids interfaces reconcile identities and dependency
representation, no store write. records_from_store(store,layer=gen) returns
GEN0062 blockedBy=[] while the same-session source has dependency333=GEN0060.
This asserts an existing gap, not a passing dependency-preservation contract.
Already tracked by TASK-THYROX-1072 and reserved vm-r: no newTASK/Providerfix.
PlanItem.depends_on and store edges are generic TASK relationships; typed
execution/construction/verification/integration roles remain analysis only.
See provider-dependency-provenance.json and reconciled.json.

## CI and persistence

Current inputhead90cc CI39369826270 initially running, then failed: both
observations retained. Actual REST log:10600 res_users ProgrammingError setup
and17 transaction-aborted InternalError teardown;26skips,1xfail,18warnings.
Signature HAPI1120; source/tests/dependencies/workflows unchanged694->90cc.
BASELINE_FAILURE setup, not10617 independent defects. Full log compressed and
hashed, no full pytest rerun. Six PR open; API110draft, noAPPROVED, no merges.

PostgreSQL existing Docker container remains Up5hours localhost5432, no other
client backends observed by read-only pg_stat_activity query. No DDL/DML or
migration; not a Thyrox Podman resource. No model inference or functional TASK.

## Persistent authority and remaining work

Docs existing analysis v1.6 plus existing dossier section31 capture fourteen
contract elements for cursor and flush, consumers and dependencies, cache vs
recompute responsibilities, taxonomy consequences and all seven obligations.
No separate master plan. Full driver/replica, actual persistence, cache-context
consumer coverage, global contractual population and acceptance remain open.
