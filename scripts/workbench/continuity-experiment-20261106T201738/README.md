# Experimento de continuidad — dónde se interrumpe el flujo

Banco de fixture (no toca el plan productivo ni claims reales) que ejecuta los
mecanismos reales:

| Paso | Mecanismo | Propietario |
|---|---|---|
| seleccionar | `thyrox: src/session/task_continuation.py next` (`continuation_frontier.runnable_items`) | Thyrox |
| abastecer una frontera agotada | `thyrox: src/session/local_plan.py supply` (`candidate_obstacle`) | Thyrox |
| asentar | `api: scripts/workbench/orm-continuation-plan-20261103T095630/probes/settle_item.py` | API |

Plan: A y B independientes, C depende de A, D necesita una credencial marcada
como expuesta, E declara `obligations: []`. Candidatas de abastecimiento: F (sin
prueba roja) y G (su prueba existe).

## Resultado (`outputs/experiment.log`)

1. Frontera inicial `A B E`; D nunca aparece (`doomed_items`: credencial
   expuesta). Con `--node`, el primero: `A`.
2. Tras asentar A: `B C E` (C desbloqueada). A no se repite.
3. E se rehúsa (exit 2) y queda `hard_block`: sale de la frontera.
4. Tras B y C: `frontera vacía`. `supply` omite F (`missing-test`), incorpora
   G y la frontera vuelve a ofrecer `G`.

Controles negativos conservados:

- `outputs/before-fix/`: sin la guarda, E (sin obligaciones) se asentó con
  exit 0 — el caso E (INC-01) reproducido.
- `outputs/after-first-guard/`: con la guarda pero sin `hard_block`, E quedó en
  la frontera para siempre y `supply` respondió `selectable: E` sin abastecer.

## Diagnóstico por caso

| Caso | ¿Ocurre? | Componente | Responsable |
|---|---|---|---|
| A — elegible no despachada | Sí: el ciclo de la sesión terminaba en la publicación sin invocar `next` ni `supply` | ciclo de unidad de la sesión | VM-x2hokp (API) |
| B — Thyrox no encuentra la unidad | No: `next` ofrece lo elegible, respeta dependencias, credenciales y repetición | — | — |
| C — obligación no representada | Sí en el plan productivo: veredicto C, 56 TASK sin unidad; `supply` exige la prueba roja escrita y nada en el Consumer producía candidatas | productor de candidatas del Consumer | VM-x2hokp (API) |
| D — límite externo | Observado antes: el clasificador de la sesión sin veredicto, contenedor reclamado | runtime | — |
| E — asiento sin obligaciones | Sí, corregido en `settle_item.py` (exit 2 + `hard_block`) | adaptación API | VM-x2hokp (API) |

Ningún defecto es del Provider: `PlanItem` no conoce obligaciones por diseño, y
la exigencia de prueba roja de `supply` es el contrato TDD.

Reproducir: `bash scripts/workbench/continuity-experiment-20261106T201738/run_experiment.sh`
(árbol limpio; `supply` añade G a `plan.jsonl` del banco).

## Aplicación al plan real

El caso C se cerró sobre el plan real con la misma vía: prueba RED
(`2f66cb99`), fila candidata, `local_plan supply` (`8dd2a7df`), selección por
`task_continuation next`, implementación (`c5be9ff0`) y asiento (`11bb3430`).

Uso de `--node`: recibe el nodo (`x2hokp`), y el Provider compara el dueño de
cada claim como `vm-<nodo>` en minúsculas. Con `--node VM-x2hokp` el supply
rechazó la unidad como `foreign-claim` sobre los claims propios. El experimento
de esta carpeta no lo detectaba porque su ledger es un fixture.
`probes/unit_cycle.sh` pasa ahora `x2hokp` y escribe los claims como
`VM-x2hokp`.

## Qué sobrevive al final de un turno (medido el 2026-11-07)

Entre el último turno del 2026-11-06 y el siguiente, el contenedor se
reclamó: `boot_id` nuevo, arranque a las 01:34:47Z, PostgreSQL caído. Murió
todo lo de segundo plano. Sobrevivieron Git (HEAD `c2cd635b`, árbol limpio),
el ledger de claims (`.claude/coordination/claims.jsonl`), el registro de
asientos (`orm-continuation-plan-*/outputs/continuation.jsonl`, nueve
unidades aceptadas en ese intervalo) y el scratchpad con el entorno de
referencia.

| Pregunta | Mecanismo | Sobrevive al reclamo |
|---|---|---|
| TASK | TaskStore de Thyrox (`agent_store.sqlite3`) | sí, en disco |
| claims | `claims.jsonl` versionado | sí |
| unidades pendientes y asentadas | `plan.jsonl` y `continuation.jsonl` del banco | sí |
| admisión | `local_plan supply`, `task_continuation next` | se recalcula al volver |
| ejecución de una unidad | la sesión conversacional | no |
| despertar al ejecutor tras el turno | ninguno de Thyrox: H-THYROX-682 (la recuperación al arrancar no tiene disparador propio), H-THYROX-633 (un `Monitor` no evita el reclamo) | — |

La recuperación es, por tanto, desde el estado durable: `task_continuation
next` y el inventario dicen dónde seguir, sin reconstruir nada. Lo que falta
es el disparador que vuelva a invocar al ejecutor; es capacidad pendiente del
Provider, no del Consumer.
