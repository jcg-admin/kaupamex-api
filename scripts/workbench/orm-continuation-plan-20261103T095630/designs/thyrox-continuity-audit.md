# Auditoría — ¿Thyrox selecciona, reclama y despacha las TASK de este banco?

Fecha: 2026-11-09, VM-x2hokp, `kaupamex-api@ae6f4e40`, `thyrox` local.
Todo lo de abajo es medido en esta sesión; donde no hay evento se escribe que
no lo hay.

## 1. Capacidades del proveedor (existencia, no uso)

| Capacidad | Existe | Contrato medido | Disponible aquí |
|---|---|---|---|
| `bin/local_plan` (`propose`, `incorporate`, `supply`) | sí | `supply` abastece una frontera agotada con la primera candidata admisible; causas de rechazo: `duplicate`, `task-closed`, `foreign-claim`, `dependency`, `resources`, `missing-test` | sí (Python local) |
| `continuation_frontier` / `node_next_task` | sí (en `src/`, sin binario propio) | usados por `task_continuation next` y `local_plan supply` | sí |
| `bin/task_continuation` (`run`, `next`, `run-one`) | sí | consume `plan.jsonl` como DAG; despacha cada ítem con `thyrox-bg --task` → `PodmanExecutionPrimitive` → `thyrox -p` con el candidato | **no**: `podman` no está instalado (`which podman` vacío) |
| `bin/implementation_order` | sí | orden por fichas de tareas | no evaluado contra este banco |
| `bin/model_coordinator` | sí | coordinador de modelos por socket | **no**: `sin coordinador sano en …/coordinator.sock` |
| `resource_admission`, `headless-pool`, `run-task-pool`, `thyrox-bg`, `wait-jobs` | sí | admisión de RAM/VRAM; pools; trabajos y barrera | `thyrox-bg`/`wait-jobs` sí; modelo local **no**: `hardware-inventory` → `none` (sin GPU) y sin unidad `model-runtime` |
| claims | `.claude/coordination/claims.jsonl` del consumidor | 1794 filas | sí |

## 2. Lo que realmente gestionó Thyrox — la cadena reconstruida

`outputs/continuation.jsonl` del banco: 367 eventos — 181 `attempt`, 180
`accepted`, 6 `hard_block`. **Los 181 `attempt` llevan
`model: "conversational-session"` y `source: "preexisting"`.** El
`run-one` del proveedor, cuando acepta un ítem ya verificado, escribe
`model: None` y añade `taskClass` y `transition`
(`src/session/task_continuation.py:1090-1091`); los 181 eventos no traen
ninguna de las dos claves. Son registros escritos por la sesión
conversacional, no por el controlador. `plan.provenance.json` lo confirma:
`planner: "conversational-session"` en cada incorporación, y los 182 ítems
declaran `candidates: ["claude-opus-5-5"]`, que esta VM no puede usar como
trabajador.

Las unidades de `_read_group` y sus vecinas (`95ec4213` … `ae6f4e40`, 21
commits del 2026-11-09 entre 19:51 y 21:44) **no tienen ítem en el plan, ni
claim** (0 filas de `claims.jsonl` las nombran), ni evento en
`continuation.jsonl`. El último evento del controlador es el `accepted` de
`tools-sql-reference-shape-0486` (19:08:05Z, `9ed30a92`).

| TASK / unidad | Selected by | Claim owner | Worker | Model | Resource admission | Started | Verification | Settlement | Next TASK |
|---|---|---|---|---|---|---|---|---|---|
| `tools-sql-reference-shape-0486` (TASK-API-0486) | manual (incorporación `conversational-session`) | VM-x2hokp (claims de rutas, liberados 19:08:08Z) | no hubo worker gestionado | conversational-session | no hubo | sin evento | `verifyExit 0` registrado por la sesión | `accepted` registrado por la sesión | no hubo evento de selección |
| `_search`/`ir.rule` (`1ae6b4a2` … `6d4c1764`, TASK-API-0397/0485) | manual | no hubo claim | no hubo worker gestionado | conversational-session | no hubo | sin evento | pruebas RED/GREEN y gates en `red/*.md` | no hubo settlement en el ledger | manual |
| `_read_group` 2-6d (`bd3e1bde` … `59a8b2e8`) | manual | no hubo claim | no hubo worker gestionado | conversational-session | no hubo | sin evento | `red/read-group*.md`, nivel 2/3 | no hubo settlement en el ledger | manual |
| `_read_grouping_sets`, `Environment` Mapping, `Properties.type` (`d31f8f48`, `453c66b8`, `9b7cabfc`) | manual | no hubo claim | no hubo worker gestionado | conversational-session | no hubo | sin evento | `red/*.md`, nivel 3 sobre `9b7cabfc` | no hubo settlement en el ledger | manual |

Clasificación: las 181 aceptaciones del ledger son **C** (integración
parcial: el ledger y el plan de Thyrox existen y se usaron como registro,
pero selección, ejecución y transición las hizo la sesión). Las unidades del
2026-11-09 posteriores a 19:08 son **B** (ejecución manual sin pasar por el
plan). **Ningún ciclo es A.** Porcentaje del ciclo gestionado por Thyrox en
la muestra: selección 0 %, claim 0 % (los claims de rutas los escribió la
sesión), admisión 0 %, despacho 0 %, settlement 0 % (escrito a mano en el
formato del ledger).

## 3. TaskStore

- El store de tareas que el proveedor resuelve es
  `thyrox/agent-results/agent_store.sqlite3` (2666 tareas de 12 sesiones;
  capa `api`: 282 `pending`, 18 `in_progress`, 204 `completed`). Ahí están
  TASK-API-0397/0485 (`in_progress`), 0486, 0399, 0401, 0479, 0182, 0504
  (`pending`).
- `kaupamex-api/.claude/agent-results/agent_store.sqlite3` también tiene
  tabla `tasks`, **vacía** para la capa `api`; `agregar-hallazgo` indexó
  ahí H-API-1207/1208. Dos archivos para un mismo esquema: se registra como
  brecha de autoridad, no se fusionan (está prohibido).
- El plan del banco no lee el store para seleccionar: `local_plan supply`
  lo usa sólo para excluir TASK cerradas. Las candidatas las debe traducir el
  consumidor a filas; **ningún proceso las genera desde el store**.

## 4. Por qué no hubo transición automática tras `ae6f4e40`

1. Fin de unidad: no hubo evento (las unidades no estaban en el plan).
2. Settlement: no hubo.
3. Liberación de claim: no aplica (no hubo claim).
4. Frontera: `task_continuation next` → `frontera vacía` (los 182 ítems
   están `accepted` o en `hard_block`).
5. Selección siguiente: `local_plan supply` sólo actúa con candidatas que el
   consumidor provea; no se le dio ninguna.
6. Admisión: no se evaluó.
7. Despacho: **imposible aquí**: `task_continuation run` exige Podman y un
   candidato servible; no hay `podman`, no hay GPU ni unidad de modelo
   local, y el único candidato declarado es Claude, que no se usa como
   trabajador.
8-9. Registro y selección posterior: no hubo.

Causas, separadas: **integración no existente** (nada convierte el store en
candidatas para `supply`), **configuración ausente** (candidatos de los
ítems = Claude), **recurso no disponible** (Podman y modelo local), y el
cierre de la publicación Git no está conectado a ningún evento del
controlador.

## 5. Qué se reutiliza y qué queda manual

Se reutiliza: `local_plan supply` para incorporar la siguiente unidad con sus
causas de admisión; `task_continuation next` para que la selección la haga el
controlador; `claims.jsonl` para reservar las rutas; `continuation.jsonl`
sólo con eventos que el controlador escriba. Queda manual, declarado: la
traducción de TASK del store a filas candidatas, la ejecución (sin worker
gestionado ni modelo local) y la verificación (la corre la sesión). No se
construye coordinador ni cola propia; no se modifica el proveedor.

Responsable de la brecha: el proveedor (Thyrox) — generar candidatas desde el
store y servir un worker local en esta VM. Se registra como hallazgo
H-THYROX en el pase siguiente si el ejecutor lo autoriza; aquí sólo se mide.
