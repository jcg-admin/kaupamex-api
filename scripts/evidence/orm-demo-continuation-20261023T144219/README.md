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

## Contractual continuation instruction, 2026-10-23

The same instruction-validation.json now contains a separate review of all
45 numbered sections of the new continuation instruction, with its source
SHA256. Historical assessments and outcomes above remain historical.
The original job manifest settlement is not a duration/status claim for
these later processes; their own logs, JUnit and tool exit codes apply.

Code commit56c6d4ea adds two independent support stages under native local737,
TASK-API-0382, still pending and owned by codex-module-lifecycle:

- _check_module_names deduplicates requests, ignores the all wildcard and
  warns only unknown names in the supplied cursor's catalogue. The actual
  PostgreSQL differential caught psycopg3 tuple-IN incompatibility; parameterized
  ANY(list) is the measured adaptation. Six initial controls fail before
  implementation.16 differential cases pass across two isolated schemas in
  one own database, including an injection-shaped name treated as data.
  This is not productive multi-database acceptance.
- reset_modules_state restores transient requests after failure, preserving
  stable states and installed_version. Django requires leaving the failed
  caller transaction before recovery; nested/manual transactions are refused.
  Native atomic commits both updates together. Four initial controls fail
  before implementation. Actual PostgreSQL verifies reference state mapping,
  independent-connection visibility, missing-table no-op and full rollback
  when a real constraint rejects the second update.

Combined data/demo/names/reset controls:26PASS. Both memory-only no-op
controls exit1 as expected. The pinned functions are extracted using existing
counterpart_body.declarations_of and reference_roots, not a new extractor.
The comparison uses actual PG SQL with explicit cursor-protocol adaptation;
it does not run native Odoo or establish whole-loader equivalence.

Selection inputs/results and native task reads are saved separately without
replacing historical exports. node_frontier was invoked with the full ledger.
Its own_owner(node)=vm-<node> does not match codex-module-lifecycle. Own code
claims were released before selection and reacquired with native overlap
checks before editing; no foreign claims or identities were filtered/rewritten.
The13 previously reviewed Provider source interfaces are unchanged; their
local-model/runtime qualification is not inferred from source equality.

The first CI in this extension started before reset was added and ended
77PASS/1SKIP/1ERROR508.87s, make2. A second CI targets exact56c6d4ea;
its definitive result is outputs/loading-support-summary.json and its JUnit.
Remote baseline5dad run39977965965 completed FAILURE,77PASS/1SKIP/1ERROR
476.44s, display_name; the complete775-line log is preserved here.

DEC-AISL-05 still leaves contenttypes/session placement open. Router/service
and the failing migration are unchanged, so valid company experiments were
not repeated. No manual production table, policy relaxation or fake PASS.
force_demo requires cache invalidation, transaction reset and registry rebuild;
load_modules requires effective composition/schema/data/hooks/finalization.
Existing Registry.new still delegates to _ensure_seeded. Its historical #342
comment is not a durable TASK identity: current native342 is TASK-API-0187,
stock work. Native targeted search found no Registry.new/load_modules text;
this is a search limitation, not proof that equivalent work does not exist.

The existing loading ledger now has five reviewed source-flow contracts and
two pending named declarations. These counts are not accepted-contract
denominators. Both existing AS IS files retain their same62-task population.
No TASK status was changed and no managed model inference, merge or whole
objective acceptance is claimed. Final continuation inputs and real blockers
remain in outputs/loading-support-continuation.json.

Final exact-code CI:77PASS/1SKIP/1ERROR482.36s, pytest1/make2,
first inherited ProductProduct.display_name; later tests NOT_EVALUATED.
All owned databases/roles are cleaned (zero remaining). Code56c6d4ea is
published and remote hash verified, PR109 open/unmerged. The first normal
commit attempt failed because its process lacked Django/reference environment;
rerun with existing venv/PATH and pinned resolver passed normal hooks.
No hook/config/baseline was bypassed or changed.

Current native ownership revalidation of the existing62 AS IS identities:
60NULL owners, only0382/0383 owned by codex-module-lifecycle, both pending.
Related compute triage is TASK-GEN-0633 pending ownerNULL;0418 also pending
ownerNULL. No claim is not ownership. Generic task_source correction1072 is
pending ownerNULL with actual vm-r source reservation; continuation source
has vm-r/vm-a reservations. No Provider state/code edit or alternate global
admission mechanism. Final frontier uses actual acceptance-gate failure, not
manufactured accepted state; it is scoped, not a global exhaustion verdict.


## Further contractual continuation: historical default and local metadata

Source commits e8ea2938 (default/migration),1e3dfe2d (exact experimental
instrument),ea963f24 (local metadata proposal) and4f5a166f (fixture safety)
are published. TASK-API-0383 remains pending, owner codex-module-lifecycle;
TASK-API-0382 remains pending. No TaskUpdate or managed model inference.

The existing45-section instruction control is reconciled with the new actual
results. Three independent source-reviewed units were selected using native
node_frontier with full claims, then conflict-checked native claims. This
continues beyond the previous partial frontier rather than reconstructing AS IS.
The old failed flags on passing support stages were projections of global CI,
not functional failures; original snapshot preserved with explicit correction.

website_sale0003 had evaluated a current runtime XMLID default during DDL.
The maintained PG control fails there before the fix. SeparateDatabaseAndState
adds nullable DDL without a live callable, preserves callable state and uses
historical local metadata/active-team backfill.0004 stays unchanged. Four
complete forward/reverse cases pass; one wrong-model identity case rejects,
rolls back and preserves the old row (the raw positive log's generic label
was corrected in the probe afterward, not counted as a fifth forward/reverse).
Two pure runtime controls verify explicit default/company router binding.
Negative separation annulment exits1 expected. Initial pytest setup with an
overscoped django_db marker was invalid, excluded from RED/PASS and retained
with generated ephemeral test values redacted. No shared QA was provisioned.

Native MigrationLoader confirms actual required historical dependency fields.
Pinned Odoo source at abe4040ec1a45beee90fb694e4eae4453e46b389 resolves the
optional team through the active Environment and accepts only an active team.
Existing14-element dependency record is in the existing per-file bank's
website-sale-default-contract.json, not full-file or whole-addon acceptance.

Controlled experiment: exact instrument preserved in1e3dfe2d, then current
proposal without any contenttypes override: both complete380migrations and
107local FK to res_users in each separate own default/company database.
Backbone tables, nullable installed_version and actual native metadata/cache
and SessionStore create/rotate/read/flush pass. Company database is removed;
root QA database/role are removed, zero owned remnants observed. The catalogue
has0rows: schema is not installation/whole module loading. Only one company
and a separate default DB were verified; this does not qualify full N=2 login,
identity switching, authorization or existing broken-database recovery.

Proposal ea963f24 keeps sessions central and metadata local using existing
configuration/router, with roster and fail-closed guards unchanged. Four
routing controls fail before and26combined controls pass after. Existing
DEC-AISL-05 retains its accepted directive and adds an explicit proposed
review subsection; no approval or merge is granted automatically.

Exact production CI at ea963f24:77PASS/1SKIP/1ERROR490.26s, pytest1/make2,
same first baseline display_name error. Independent company verifier exits0;
combined process retains2. Previous e8ea2938 CI:77/1/1,501.29s, make2,
experimental company verifier0. These are separate runs, not summed coverage.
Source production bytes remain identical to ea963f24; later fixture-only
changes have3focused PASS and are not represented as full-head CI acceptance.

Legacy isolation fixture previously dropped both fixed names even if creation
failed.3negative controls fail before and pass after ownership tracking.
It now refuses existing aliases/DBs, drops only successful tracked creations
and uses the native full provisioner.3isolation cases remain skipped with
corrected reason: private TestCase overrides/fixed aliases still unqualified.
Mock controls do not certify partial SQL creation/extension-failure cleanup.
No private connection bypass was executed as part of this new verification.

Current summary/continuation: salesteam-policy-summary.json and
salesteam-policy-continuation.json. Both62-task AS IS files updated only for
0382/0383. Next logical obligation is fixture qualification and real isolation,
with approval/acceptance/identity and whole Registry/loader kept separate.
No global exhaustion, complete instruction or complete ORM is declared.

## Continuación integral: fixture y cobertura por archivo

La instrucción de continuación integral queda reconciliada en
`outputs/instruction-validation.json#integral_continuation_instruction_review`:
55 secciones, sin declarar completa la iniciativa. No se abrió otro expediente,
TaskStore, coordinador o población maestra. Las 62 TASK de los AS IS se conservan.

Fuente publicada: `4b67be0f` cualifica el fixture de TASK-API-0383 mediante el
blocker público, aliases aleatorios y creación exclusiva; ExitStack registra
sólo recursos adquiridos e intenta las demás limpiezas si una falla. El default
requiere declaración explícita de recurso propio y revierte el caso N=1.
`948c5233` corrige exclusivamente el docstring del paquete modules; su AST
executable coincide con4b67be0f. No implementa el cargador que sigue pendiente.

Resultados independientes, no una suite sumada:

- Los 8 RED iniciales son ausencia de la nueva interfaz del fixture. Después 8 PASS
  de fallos/ownership. No se presentan como 8 borrados inseguros observados.
- Anulación sólo en memoria del guard de recursos existentes: 2 FAIL y 6 PASS,
  salida 1 esperada. Los casos comprueban conducta, no sólo presencia de métodos.
- PostgreSQL real: testigo preexistente preservado, DDL parcial propio limpiado,
  fallo de conexión para extensiones conserva la base adquirida para limpieza.
- Cinco casos reales PASS,2warnings heredados,915.37 s, pytest 0. Incluyen los 3 casos
  históricos antes omitidos, N=1 y esquema/conexiones sin override privado.
  Dos empresas distintas usan el provisionador completo. La corrida delimitada
  no carga el conftest global ni re-siembra sus datos fuera de migraciones.
- Gate local exacto 4b67be0f: 77 PASS, 1 SKIP, 1 ERROR en 467.74 s, pytest 1, Make 2. CI remoto
 948c5233, run 40031305381: 77 PASS, 1 SKIP, 1 ERROR en 484.20 s, Make 2. Primer fallo heredado
 ProductProduct.display_name; pruebas posteriores NOT_EVALUATED.

Dos errores del instrumento se conservan y no se convierten en fallo del
producto ni en salida 0 ficticia. El primer probe terminó 1 al inyectar un fallo
que afectaba también mantenimiento; su fuente compilada se preserva en
`probes/verify_isolation_qualification.initial.py.source.txt`, su resultado en
`outputs/isolation-qualification-initial.json` y el log
`outputs/isolation-ci-and-functional.log`. La fuente del disco fue corregida
para la reanudación, pero el proceso inicial seguía ejecutando la versión ya
compilada; no se edita su traceback para ocultarlo.

La reanudación `--bounded-only` no repitió CI. Aprovisionó un nuevo default propio
y ejecutó los 5 casos. Después pytest restauró su blocker y rechazó una consulta
Django del postcheck fuera del contexto permitido. El resultado total sigue 1,
aunque pytest terminó 0 y los aliases ya estaban retirados. Se preservan fuente
`probes/verify_isolation_qualification.postcheck-failure.py.source.txt`, log
`outputs/isolation-functional-resumption.log`, JUnit y resultado raw
`outputs/isolation-qualification-completed-tests.json`.

El harness exterior eliminó default y rol. La verificación independiente por
mantenimiento PostgreSQL terminó 0 y confirmó cero recursos propios conocidos
pendientes: `outputs/isolation-cleanup.json`. El probe actual usa mantenimiento
para ese postcheck; no se repitieron 15 minutos válidos sólo por esa corrección.
No se afirma que el instrumento completo corregido haya sido ejecutado otra vez.

Reproducción futura: en un checkout aislado de la revisión a verificar, usar el
harness `orm-bootstrap-compute-20261021T210528/probes/qa_context.py` con
`uv run --frozen python` y ejecutar `probes/verify_isolation_qualification.py`
dentro de ese entorno. Las variables Docker/host/bridge y dependencias nativas
son las de `docs/ci-local.md`; declarar UV_CACHE_DIR en el workspace. El modo
normal ejecuta el gate y los controles. `--bounded-only` fue una reanudación
exacta de 4b67be0f que exige su evidencia inicial; falla cerrado ante otro HEAD.
No se debe usar para presentar CI de otra revisión como satisfactoria. En replay
se conservan salidas separadas; los resultados históricos de este job no se
sobrescriben. Ningún comando modifica .env, Git identity, hooks o QA compartida.

`outputs/isolation-schema-observations.jsonl` es observación concurrente, no
aceptación. Mide default y primera empresa: 380 migraciones y 107 FK; la última foto
de la segunda todavía estaba migrando: 344 migraciones y 99 FK. El provisionador terminó después
y los 5 casos pasaron, pero no se inventa una medición final de 380/107 de esa base.

El banco por archivo conserva 19 declaraciones del grafo. Loading tiene 7 registros
de función, con force_demo/load_modules, consumidores reales, 14 elementos,
transacciones, hooks dinámicos y aceptación not_verified. Eso es cobertura de
las declaraciones representadas, no aceptación de sus obligaciones completas.
La dependencia encontrada de selección por petición se resuelve nativamente como
TASK-API-0381, pendiente sin propietario, fuera de la población histórica de 62; no se toma
por disponible ni se crea otra TASK.

Thyrox: 13 fuentes previas sin cambios, Bun 1.4.0 y Python 3.12.14 propios observados;
TaskGet, claimsCommand y node_frontier son las interfaces usadas. TaskSource aún
omite owner/dependencias y mantiene reservas ajenas. No hubo ejecución de modelo
local/remoto, integración automática ni cambios oficiales de estados.
`outputs/isolation-native-continuation.json` preserva entradas/ledger real:
selecciona otra vez la unidad no aceptada, no una frontera global agotada. No se
repite una prueba válida ni se fabrica accepted para liberar el cargador.

Resumen y límites: `outputs/isolation-qualification-summary.json`. Pendientes:
revisión de la propuesta DEC-AISL-05, gate global/ownership de compute, TASK-API-0381 para
resolución por petición y aceptación HTTP, recuperación histórica, Registry y
cargador efectivo, descubrimiento/admisión global e inferencia local cualificada.
Los PR permanecen abiertos; publicar evidencia no es merge ni aceptación.

### Continuación: esquema histórico aplicado (TASK-API-0383)

Selección nativa y ownership conservados en `outputs/schema-preflight-selection.json`.
`src/service/db.py` comparte contexto destino y comprobación previa entre alta
y lote; el lote no crea bases ausentes. No se repara el historial.
RED: 2 FAIL/11 PASS, exit1. GREEN:17 PASS, exit0. PostgreSQL propio:
estado parcial válido, tabla ordinaria ausente, M2M ausente, exclusión nativa
de sessions y conservación de historial/sentinel verificados, exit0 por recurso.
Anulación en memoria: rechazo desaparece, control falla exit1 esperado.
El primer experimento detectó un TypeError real de adaptación a Django;
se preservó el fallo y se corrigió a una secuencia de nodos.
El resumen contractual y los límites están en `outputs/schema-preflight-summary.json`.
No acredita columnas, reparación, aceptación de TASK ni cumplimiento global.

Gate local de ``2807e5ba``: 77 PASS, 1 SKIP, 1 ERROR, 455.78 s;
pytest1/Make2, primer fallo heredado ProductProduct.display_name,
comprobado también en CI remoto de a699454f. JUnit y log completos
`outputs/schema-preflight-ci.junit.xml` y `outputs/schema-preflight-ci.log`.
Pruebas posteriores NOT_EVALUATED; no aceptación global ni merge.
