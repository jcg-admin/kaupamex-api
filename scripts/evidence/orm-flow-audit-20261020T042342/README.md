# ORM flow audit and compatibility design

Continues existing audit, no functional implementation or taxonomy migration.
Consumer API 694587d9a5b6715e1e0309e7c8b36c58d8ebdc2d; Docs
01efd5f58f5f9a737e55bc979800cecc8998fd09; Provider
9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f; reference Odoo
abe4040ec1a45beee90fb694e4eae4453e46b389.

## New behavioral verification

Exact Environment.invalidate_all bodies extracted with existing
extract_both_sides.bodies. Four protocol cases and an in-memory mutant:
default/True lack flush in Consumer; False agrees; a failing reference flush
propagates without invalidation, Consumer instead invalidates. Assertions exit 0
by detecting the gap, not by accepting the contract. No Django setup, database,
product mutation or full Odoo runtime. PostgreSQL data loss is not demonstrated.
Sources, bodies and hashes are in invalidate-all-observations.json.

Reproduce from API checkout with reference_roots configured for the revision:
UV_CACHE_DIR=/workspace/.cache/uv ODOO_TOOLS=<verified-reference-root>
uv run --frozen python <run>/outputs/probe_invalidate_all_flow.py
THYROX_CONSUMER is optional when root discovery reaches scripts/reference_roots.py.
One initial scratch execution and one rerun justified by portable root discovery;
no unchanged historical experiment was repeated.

## Existing Provider mechanisms actually used

Provider revision above. session.job_runs.jobs_dir(start), scaffold_run(base,slug,
command); workbench.manifest.declare_workbench(run,question,instrument,metric,
blind_to); settle(run,exit_code); TypeScript checkWorkbench(run). Creation and
settlement describe this audit job, not local-model execution or a functional TASK.
claimsCommand --claim/--release --owner codex-flow-audit --branch
feature/codex-workspace-bootstrap reserves only these evidence/document paths.

Identity/store: agents.agent_store.resolve_store_dir(create=False),
connect_readonly; task.task_ids.mapping_from_store and lookup. Nine stable
identities; owner NULL throughout. JSON reciprocal dependencies GEN0060/0062,
text-only dependencies API0417/0418/0419. No state changes or eligibility claim.
Native bin/task_ids lookup commands, exit codes and full errors/warnings are
in lookup-results.json and lookup-explicit-board-results.json. Default board
access fails; explicit unavailable historical board allows identity resolution
but cannot establish board ambiguity checks. Text searches do not prove absence.
Read-only API chosen because buscar-tareas connect() would migrate/resync FTS.

## Remote and infrastructure evidence

Six PR snapshots in pr-state.json. API694587d9 CI39357612617 fails setup:
sync_apps creates FK test_orm_testormdiscussion.moderator_id -> res_users missing.
10617 setup errors are not 10617 independent functional defects. No changes
src/tests/dependencies/workflow since61ea5e9f; signature H-API-1120 baseline.
Full actual log is compressed here; original size/hash in log-provenance.json.
Empty exit0 gh --log-failed was rejected as insufficient; REST logs were used.
No full pytest/Sphinx run, no gates weakened, no PR merged.

PostgreSQL docker ps reports existing container Up4hours localhost5432; read-only
pg_stat_activity client query excluding own backend returns zero rows, exit0.
No DDL/DML or migrations this batch. This is Cloud Docker, not Thyrox Podman.
Provider podman/llama-server/ollama absent by PATH/process probes, no inference.
Claims snapshot preserves other owners and is not evidence of live workers.

## Persistent analysis

Existing Docs authority analisis-contrato-de-basemodel-trae-o-construye.rst v1.5
records matrix by classifier, historical methodology, 14-element contract tables,
canonical English candidates, compatibility constraints, TASK graph and seven
closure obligations. Existing bootstrap dossier is updated, not replaced.
Several material obligations remain not_verified, especially whole-family
population, reference tests, persistence, accepted ownership and execution.
