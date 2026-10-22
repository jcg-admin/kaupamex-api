# TASK-API-0382: dependency-anchored test addon order

Continues API fc2ff8c8, Docs67239a5f5. Pinned reference remains Community19
abe4040ec1a45beee90fb694e4eae4453e46b389. Existing pilot/inventory was consulted
before implementation; no new census/extractor, graph or TaskStore.

## Atomic contract and implementation

Reference ModuleNode.depth/order_name and ModuleGraph.__iter__ determine
placement. Normal addon depth is max dependency depth+1 (or0) and key is its
name. test_* shares its latest dependency's depth and uses that dependency's
key plus a space and its name. Consumer now follows these rules. No-argument
static graph API remains; dependency-cycle detection still raises its domain
error. Keys are evaluated against current dependencies, not cached forever.

Existing consumers include IrModule administrative dependency closure and
ModuleGraph.auto_installable. This unit requires only the existing manifest
parser and pure graph; DB-bound load phases are not its prerequisites. Full
loader execution, state filtering, demo eligibility and registry composition
remain separate pending contracts; requests do not mean installed execution.

## Admission and mechanism

Native TaskGet737 in session168b0fdf-bfe4-590b-b6c0-b6be124c124a returned
TASK-API-0382 pending owned by codex-module-lifecycle. Prior DEC-AISL-05 and
0382 admission are retained, not inferred from empty declared edges.
Provider revision9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f. Native interface,
claim reservation/release and job metadata are recorded in admission.json,
native-task-0382.json, Consumer ledger and manifest. No TASK status/owner writes,
no local Provider inference, no external model or second coordinator.

## Verification

- baseline.log:2FAIL/3PASS,exit1, before implementation.
- conformance.log/JUnit:17PASS,exit0. Seven original inventory tests and ten
  bounded contract cases; phase/demo controls still document pending behavior.
- regression.log/JUnit:12PASS,exit0, existing pure graph tests. Isolation uses
  --confcutdir=tests/unit/modules, with import-only settings. These tests do not
  access a DB and are not a replacement for global PostgreSQL verification.
- Global ci-verify uses the existing qa_context disposable PostgreSQL mechanism,
  native build prerequisites and frozen uv. Full output in outputs/ci-verify.log;
  definitive result:pytest1/make2,77PASS/1SKIP/1ERROR in532.98s.
  Exact error matches the preserved pre-change remote JUnit: ProductProduct
  display_name assignment. Later suite NOT_EVALUATED, global acceptance blocked.

Actual invocations and detailed14-element ordering contract are in outputs.
Source header claims were not treated as contract authority; outdated static
lifecycle justification and cycle explanation were corrected from source.

## Reproduction and continuation

Use the existing pinned resolver ODOO_TOOLS; reference bodies are reused
unchanged via counterpart_body.declarations_of. Run frozen uv pytest on the
existing inventory test directory. The exact workbench test source is there;
no extra AST extraction algorithm was introduced.

Existing AS IS source group model_registry_extension_semantics links this unit.
Prior pilot snapshots remain historical, not regenerated against new behavior.
Acceptance requires review/CI and authorized integration; no merge in this lot.
Next dependency frontier: database-state graph snapshot and load/update pruning,
then loader phases/composition/schema/data/hooks and worker invalidation. No
whole ORM or installation acceptance from this bounded ordering correction.

Cleanup confirmed0remaining disposable databases/roles. No bypass or merge.
