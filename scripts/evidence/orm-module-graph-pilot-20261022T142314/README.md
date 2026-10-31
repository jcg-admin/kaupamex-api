# ModuleGraph: incremental contractual verification

Continues TASK-API-0382 from API 0d4de26b, Docs d8ccb209c and Thyrox
9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f. Reference remains
abe4040ec1a45beee90fb694e4eae4453e46b389, Community19.

## Results

- Existing inventory `file_inventory/declared_symbols` actually executed on
  the pinned ModuleGraph and Consumer. Output stays in the existing inventory
  run, `outputs/module-graph-pilot.json`, not a new general census.
- All18 class/method declarations have dispositions and the existing14
  contractual dimensions. Manual full-source review adds the nested phase
  helper, imports, conditional type alias, logger, attributes and bases.
  Historical extractor limitations remain explicit. No new AST extractor.
- Five new Consumer/reference contract probes PASS; seven original reference
  inventory tests PASS. Reference class bodies are unmodified, but the probes
  bypass constructor/native fixtures, so these are not Odoo-native integration.
- Ordinary depths and Consumer membership/lookup/cardinality verified.
  test_* placement/depth/order differ. Reference load/update phases and demo
  dependency eligibility exercised; current static Consumer does not implement
  them. No loader, migration or worker acceptance from queued requests.
- Four specialized historical instrument suites:62PASS,exit0.
- Joint initial instrument run:18PASS/1FAIL,exit1. Preserved failure is a
  fixture anchored to registry constructor line844; current owner
  _ConstraintMethods.__init__ is at979. No completed TASK reopened or tests
  weakened. `pilot.log` and `specialized.log` are separate bounded results.
- Native TaskGet1153/1154 confirms completed0391/0392;737 confirms pending0382
  owned by codex-module-lifecycle. No task state/owner writes or new TASK.
- Existing alias resolver reused. Pinned complete Git tree has no literal auth
  addon in either Community root. Eight authz_* aliases exist; no blanket
  auth->authz rewrite. Authorization equivalence remains not_verified.
- CI39719704981:completed/failure at0d4de26b, PR109/154 open and unmerged.
  `gh run view --log-failed` exit0 produced zero bytes; no cause inferred.
  Previous local ci-verify FAIL remains independent evidence, not rerun for
  verification-only additions. No production API behavior changed.
- Both /tmp recovery copies match persisted copies; no mutation replay.

## Reproduction

Set ODOO_TOOLS to the pinned read-only Git checkout. Use the existing
`/tmp/orm_batch_env.py` import-settings launcher, whose recovery source and
hash are in `outputs/preservation.json`. No six .env files are modified.

    uv run --frozen pytest -q scripts/workbench/odoo-orm-reference-inventory-20260910T181517/tests --confcutdir=scripts/workbench
    uv run --frozen python scripts/evidence/orm-module-graph-pilot-20261022T142314/probes/reconcile_module_graph.py

The second command incrementally reconciles this one pilot, not a general
extractor. Native interfaces, revision, limits and original manifests are in
`outputs/instrument-authority.json`; native task JSON, remote observations,
JUnit and terminal logs are in outputs. No local-model inference occurred.

## Continuation frontier

Existing AS IS source group model_registry_extension_semantics links this
pilot. The test_orm corpus remains its original scope, not a denominator for
odoo/modules. No global inventories regenerated, no official states changed.

Under0382, continue a database-bound executable graph with load/update pruning,
then schema/model composition/data/hooks/invalidation and worker consistency,
using dependencies and claims before each unit. test_* placement is now a
bounded proven difference available to that planning. Base/authz bootstrap
cycle0173 remains unowned, not automatically eligible. Compute0417 and CI
acceptance remain unresolved; requests are not executed installation. This
batch advances admitted verification, not production loader implementation.

Claims reserved/released through native claimsCommand, recorded in Consumer
ledger. Job scaffold/declaration/settlement use Thyrox interfaces. Overall
job exit1 preserves historical instrument failure; manifest conformity is
not contract acceptance. Publication is feature PR only, no merge.
