# Current-instruction validation and demo continuation

Objective `completar-raiz-orm`: **incomplete**. The initial2026-10-23 job
started with owned TASK-API-0382/native737; its observations below remain
historical. Later explicitly authorized owner-only and description-only native
TaskUpdate operations are recorded in this same job. Official states remain
unchanged; no new TASK, model inference, merge, protection change or TASK
taxonomy migration is claimed. Domain module-category migration0090 is separate.

`outputs/instruction-validation.json` reviews clauses0..56 of the initial
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

### Extensión incremental vinculada: TASK-API-0382

`312b7fb6` reutiliza la preparación del grafo dentro de extensiones vinculadas
a un alias. RED3FAIL13PASS -> GREEN16PASS; controles vecinos65PASS en otra
ejecución. PostgreSQL propio verifica alias, estado/demo/versión, poda y fase
sin escrituras del grafo.12comparaciones incrementales de cuerpos fijados PASS;
los adaptadores se declaran en el resumen. Anular preparación o forzar alias
default causa fallos esperados1. Los errores de instrumento de los primeros
diferenciales se conservan; no son regresiones productivas ni PASS.
Autoridad contractual: banco existente `module-graph-contract-reconciliation.json`,
sección `incremental_extension`; resumen y registros `outputs/incremental-graph-*`.
No demuestra instalación efectiva, dos bases de empresa, aceptación ni merge.

Gate local312b7fb6:77PASS1SKIP1ERROR429.67s,pytest1/Make2; primer fallo
heredado ProductProduct.display_name, comprobado también en JUnit remoto479f02c6.
JUnit/log completos en `outputs/incremental-graph-ci.*`. Lo posterior al primer
error queda NOT_EVALUATED; la aceptación integral sigue pendiente.

### Continuación contractual exhaustiva: grafo físico y fixture actual

La instrucción se preserva en `inputs/contractual-continuation-20261024.txt`;
sus54secciones extienden instruction-validation.json, sin otro plan o maestro.
Los bancos existentes del grafo/cargador relacionan responsabilidades compuestas
con19declaraciones y7funciones. No son denominadores de aceptación.

Dos bases físicas propias prueban la selección incremental de catálogo:
positivo0, alias incorrecto1esperado, adquisición parcial1esperado; limpiezaPASS
en los tres escenarios. Los catálogos mínimos no acreditan Registry ni auth.

El fixture actual3fb301a5 pasa5casos en878.16s,pytest0 yprobe0, con el
provisionador completo después del preflight2807. Los controles de recurso
preexistente,DDLparcial yfallo deextensiones pasan. Postcheck ycomprobación
independiente exacta confirman cero recursos conocidos. No se sobrescriben
resultados previos4b67be0f ni se retiran protecciones privadas para forzarPASS.
Se reutilizaCIlocal312Make2 sólo tras igualdad exacta de fuentes/pruebas/gate;
elJUnitremoto3fbactual también conserva primerfallodisplay_name yresto no
evaluado. No se repite una compilación global por cambios sólo de evidencia.

TaskGet confirma0264completada. Tras dos autorizaciones explícitas del usuario,
TaskUpdate asignó sólo owner=codex-module-lifecycle a0265/0269/0267/GEN0633.
Los cuatro estados pendientes y dependencias permanecen iguales, ver los dos
archivos contractual-*-ownership-assignment.json.0381/0418 siguen fuera de
esa asignación. Las propuestas anteriores se conservan como historia.
update_module_list ya existe: estado TASK no es ausencia de código.
No se cambian estados, dependencias, política ni gates.
Las13interfacesProvider comparadasno cambiaron; no hubo inferencia gestionada.

0269:5744db36 selecciona apps instalables antes del registro Django mediante
el grafo existente; RED3FAIL2PASS, GREEN21PASS, arranque nativo positivo0 y
anulación1. La selección actual124addons/125LOCAL_APPS conserva orden y
miembros. No acredita composición por base ni exclusión de todo import.
El gate local conserva77PASS1SKIP1ERROR, Make2 por display_name.

0265:5a84f1ff añade el recurso HTTP técnico de sólo lectura, capacidad explícita,
paginación y filtros tipados, sin selector de conexión ni instalación. RED9FAIL,
primerGREEN7PASS2FAIL por sobre de error, corregidoGREEN55PASS con regresiones
vecinas y OpenAPI. Contrato14 en technical-catalogue-contract-14.json.
El hook usa la interfaz existente IDENTIFIER_LANGUAGE_CANON_KEYS=codigo_error
por invocación; se preserva el rechazo inicial y no se modifica el baseline.

GEN0633:los64nodeid históricos se recuperaron del log diag3-353 completo.
historical-64-selection.json conserva selección nativa, entradas y ledger sin
aceptaciones inventadas. El triaje debe conservar resultado actual por identidad,
contrato vigente y TASK relacionada; no asumir que los64rojos siguen iguales.
No se declara terminada la iniciativa ni cualificado un modelo local.

Resultado final del lote HTTP: CI77PASS1SKIP1ERROR436.56s, Make2 por
display_name heredado; lo posterior NOT_EVALUATED. Triaje exacto64:9PASS55FAIL
en2.40s;5fallos de asignación,37expectativas a reconciliar y13otros. Un nodeid
tiene sucesor demostrado en8b6ea823. Se preservan dos intentos de instrumento
con salida4, sin atribuirlos al ORM. Harness0 y consulta independiente0:
cero bases y roles orm_bootstrap restantes. Continúan pendientes las
correcciones contractuales, categorías, aceptación e integración.

## Display-name assignment continuation, 2026-10-25

TASK-GEN-0633 remains pending, owner codex-module-lifecycle. Native description
reconciliation preserves state, ownership and dependencies. Source c2d0d10d
restores generic/ResPartner assignment and shared descriptor invalidation.
Four disjoint verifier batches pass:50+40+165+16; exact historical64 changes
from9PASS55FAIL to14PASS50FAIL, with five resolved nodeids retained.
The c2d required CI exits2:77PASS1SKIP1ERROR, ProductProduct missing assignment.
That first error is not the complete set of remaining suite failures.

The next native-selected unit, source2b249be8, restores ProductProduct
assignment with actual dependencies and existing Django m2m_changed -> modified
notifications for forward/reverse relationship updates. Twelve contract cases,
54 consumer cases and106 regression cases pass in separate processes against
owned PostgreSQL. Negative return-only and exception controls pass. The first
consumer invocation failed because pg_isready was absent from PATH; its actual
exit1 is preserved and the corrected invocation exits0.

The complete gate for2b249be8 exits2:146PASS1SKIP1FAIL in469.44s, first
ResCompany.country_code KeyError. Exact ae949aa8 targeted comparison also
fails, with a distinct ResCountry.DoesNotExist; the errors are not conflated.
The new stale-map regression is being corrected in the existing owned TASK. Full product context/vendor/company semantics, custom
M2M target keys, symmetrical relations and per-database cache are not qualified
by this bounded unit. No source-wide acceptance, TASK state change, merge or
local-model inference is claimed. See display-name-assignment-contract-14.json
and product-display-name-contract-14.json in outputs.

Native continuation selects TASK-API-0267.category_tree. Task452 is pending
and owned; actual modules.db exists with capability probes, contrary to older
TASK wording. Broader TASK-GEN-0058/native298 remains pending without owner;
this does not authorize completing or closing that task. Source edits wait
for the active gate to settle. Current API route returns/filters category
text, so a later FK migration must preserve that Consumer contract and data.

## Verified category/compute checkpoint, 2026-10-25

Production commits c2d0d10d,2b249be8,f1e2386f,5943be0c preserve separate
assignment, invalidation, Product Consumer, lazy-derived-map and category
contracts. Category final verification:78PASS;5historical-schema controls
PASS; alias guard RED1/GREEN0;2maintained error-storage controls PASS.
The two older catalogue probes include the new real FK dependency and retain
16names differentials, recovery state/version/rollback controls and independent
resource cleanup0. Initial failed instrument invocations are preserved.

Current full make ci-verify against exact5943be0c exits2 in474.59s:
146PASS1SKIP1FAIL, ResCountry.DoesNotExist at the tax-tags endpoint.
Exact ae949aa8 targeted comparison reproduces that exception. The newly
introduced computed-group KeyError was independently discriminated and fixed
in f1e2386f. Later full-suite tests/stages remain NOT_EVALUATED.
Sphinx NOT_EVALUATED; no build repair or protection relaxation performed.

Exact known historical64 replay stays14PASS50FAIL. Extracted pinned property
bodies and SQL-order declaration demonstrate a contradiction in two historical
fixtures: nonstored Char retains varchar/order2, and native _auto_init skips
nonstored fields before update_db. No production property or assertion was
changed to force PASS; native criterion reconciliation is the next owned
GEN0633 unit. That extracted-body experiment is not a native Odoo runtime.

The interrupted earlier QA resource was matched to previous CI by exact
owner, zero connections, schema0089 and migration timestamp45.78s before its
log ended. Targeted cleanup and independent absence checks exit0. The
current category QA lease remains active for continuation; no current
resource-cleanup completion is claimed. The secondary compatibility lease
was removed by qa_context and independently verified absent.

No full-file or initiative acceptance, effective Registry-per-database
composition, complete loader, managed local-model cycle or merge is claimed.
Unowned in-progress TASK-API-0397 and broader TASK-GEN-0058 are not available
for execution by inference. Continue native TaskGet/claims/frontier with
current contracts; a bounded candidate list is not global population coverage.


## Computed relation and historical criteria checkpoint, 2026-10-25

Source093cdfd7 reconciles schema/cache fixtures after pinned contract proof:
61PASS, exact64replay16PASS48FAIL; two fixture criteria, not two runtime fixes.
Source09974556 preserves optional nonstored Many2one None at Django raw-ID
boundary and native object-cache invalidation. Nine controls and fiscal
consumers are included in89PASS; expanded45PASS4FAIL match prior display tests.
Required full make ci-verify09974556 exits2:826PASS1SKIP1FAIL621.45s,
first missing Incoterm in the sale-stock PDF. Exact parent093cdfd7 reproduces
same assertion using identical helper sources/binaries; first skipped baseline
is retained asNOT_EVALUATED, not a PASS. Later suite remainsNOT_EVALUATED.

Source875a4aeb reconciles the superseded NonStored checker with registered typed
computed/searchable Char metadata and its assignable descriptor. Six new negative
controls preserve structural rejection;23PASS, CLI391models exit0. Stable
deletion nodeid now verifies native lack of Python deletion plus existing field
cache invalidation/recompute. Exact64replay20PASS44FAIL; four criteria, not four
new productive compute fixes. Full875a4aeb suiteNOT_EVALUATED; prior failing CI
is not a whole-head PASS. No new persistent schema or BaseModel change.

The portable Incoterm diagnostic proves direct relation, Django template,
combined extension and notes.incoterm retain the text; business counts unchanged
after rollback. Root cause of downstream PDF loss remains pending; no speculative
ORM repair. Failed etree/string and probe import-path attempts retained.
Native TaskGet confirms0264completed, so historical0382decision blocker is
reconciled description-only. Registry.new/load and Environment.registry current
source boundaries remain documented, not accepted. Historical342notfound in
checked legacy session,0391/0392completed inventory-only; no identity invented.
Provider interfaces used remain9b13f2d7 with published executable byte provenance
recorded separately. No managed inference, official state change or merge.


## Explicit inverse and new-row notification checkpoint

Sourcec4055e1c normalizes actual Django row shapes, eagerly snapshots source
values without hashing unsaved rows, and persists real stored scalar targets
at explicit inverse dispatch using the bound alias. Twelve new controls and
existing consumers total109PASS; independent SQL probe verifies name/BIC and
unchanged row counts after rollback. Normal assignment remains0SQL.

An omitted existing protocol control detects NEW_REGRESSIONc4055e1c on target.pk:
1FAIL1PASS; isolated exact parent-method replay2PASS. The known-bad full gate
is interrupted by verified own PID:310PASS1SKIP,pytest2,Make2. Sourceb87396fa
preserves non-Django targets and the unchanged existing protocol tests pass2.
Expanded129PASS1FAIL exposes a separate unsaved ResPartner notification failure.
Exact093targetFAIL and exactae949targetPASS prove a shared-setter regression of
this session, not accepted inherited debt.

Source2137fad6 respects native collection PK preconditions, retains direct and
custom in-memory inverse traversal, and invalidates contextual values using the
existing NewId cache identity. RefinedRED6FAIL3PASS; boundary-only2FAIL7PASS;
complete32PASS with9new controls; expanded180PASS. BaseModel class AST unchanged,
without claiming its inherited behavior or full recordsets accepted. Exact64
remains20PASS44FAIL;21new discriminating tests do not change that denominator.

Full required gate2137fad6:838PASS1SKIP1FAIL607.55s,Make2, first Incoterm PDF.
All12new inverse cases occur and pass in thisJUnit. Later suiteNOT_EVALUATED.
Direct compiled helper includes the note in both JSON key orders, no stale
binary demonstrated. Pipeline probe identifies selected_viewNone and missing
notes in actual helper payload: stored primary typeqweb versus canonical
filtertemplate. Historicalsale0002/sale_stock0003 assume a laterbase0070 rename
without ordering dependency. No fixture data/gate/recorder/history edit to
force PASS. Bootstrap coherence requires next native admission and verification.

The interrupted prior QA lease43562547fb9c was ownership/zero-connection checked,
cleaned using existing harness finally operations, and independently absent0/0.
Current own lease5404af94c0df remains active for continuation; cleanup not yet
claimed. Native editing claims release/reacquisition and publication checks
are preserved. No official state change, managed inference, acceptance or merge.


## Continuación: vistas, categorías y campos fiscales

Sourceebb08d93 completa el mapeo vigente base0070 para dos seeds tardíos,
sin reescribir historia, enum, esquema o resolver.22PASS y alias secundario
PASS conservan valores e idempotencia. Gate real1230PASS1SKIP1FAIL646.59s,
Make2/Pytest1: PDFIncotermPASS; primer fallo fiscal default_get. Exact093
reproduce el TypeError. El CI remoto77ce83a6 confirma el anterior fallo
Incoterm838PASS1SKIP1FAIL; ninguno acredita aceptación del head nuevo.

Sourcec2d8fce8 asigna display_name de categorías y conserva el setter
compartido para el ID de FKs ordinarias con lectura/caché nativas.
RED3FAIL; sólo asignación44PASS1FAILreparent; solución108PASS y ampliación
122PASS, incluidos ID/objeto y0SQL. Contrato14 preservado; gate propio pendiente.

Sourcef3623e31 conserva tres defaults fiscales de sesión y cuatro cómputos
según declaraciones fijadas, asigna grupos de país, usa DefaultGetMixin en
ResBank y separa conjuntos activos en la clave existente de caché.
RED23PASS16FAIL; declaración36PASS3FAIL; luego2cachepurosPASS y7modelos
metadata/setupPASS. La ampliación de caché40PASS7ERROR requierePG en siete
fixtures: no equivale a siete defectos productivos ni a una suite aprobada.
El intento sinPATHfalló antes de pruebas y permanece separado.

La revisión automática primero impidió ejecutar la última verificación por
límite de uso. Después desapareció la terminal16809. El recurso propio
orm_bootstrap_5404af94c0df sigue presente, propietario exacto y0conexiones
verificados. La limpieza exacta por operaciones finales del harness fue
rechazada antes de ejecutarse por falta de autorización explícita para
DROPbase/rol y retirada de su líneaHBA. Se solicitó permiso y no se eludió.
No se declara limpieza ni resultado fiscal PostgreSQL.

Se conservan62filas ASIS,19/7registros estructurales y el replay64previo;
las vistas relacionadas actuales incorporan estas unidades sin aceptarTASKs.
Commits locales/hooks preservados; publicación posterior a la comprobación
requerida permanece pendiente. PR109/154 abiertos sin merge en consulta real.
No estados oficiales, inferencia local gestionada, aceptación integral ni
finalización de completar-raiz-orm.
