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

## Reclamo observado con una suite en segundo plano (2026-11-07)

La suite completa de la unidad `orm-models-name-create-reference-0485` corría
en segundo plano con un `Monitor` que sólo emitía en cada 50 %; el contenedor
se reclamó a mitad de la ejecución y la suite se perdió sin resultado. Al
volver: `uptime -s` 2026-11-07 05:06:17, `boot_id` nuevo (`aa446e65`),
PostgreSQL caído (`pg_ctlcluster 16 main start` lo recuperó), y el árbol, los
claims y el scratchpad intactos. La suite se repitió completa con un `Monitor`
que emite cada 10 % y anota el `boot_id`: terminó sin otro reclamo
(12196 passed, 5 errors de `test_multidb_isolation`).

Es coherente con la hipótesis de H-THYROX-682 —cuenta el turno, no el
`Monitor` armado— y no la prueba: no se registró el instante exacto del
reclamo ni la última emisión anterior a él.

## Qué hook `Stop` gobierna esta sesión (medido 2026-11-08T00:15:42)

La instrucción 3.2.11 §9 pide investigar `stop-gate-hallazgo-pendiente.sh`
antes de tocar nada. Lo medido:

- **El gate existe con otro nombre.** Se renombró a
  `kaupamex-docs: .claude/hooks/stop-gate-pending-finding.sh`
  (`docs@a7488c264`); `docs@9ef85d240` lo apuntó a la primitiva del
  transcript. Vive en el `Stop` de `kaupamex-docs/.claude/settings.json`, con
  otros cuatro (`stop-gate-unpublished-work.sh`, `stop-gate-pending-wait.sh`,
  `stop-gate-stale-board.sh`, `reconcile-store-on-stop.sh`).
- **Ninguno de esos carga aquí.** La sesión corre con cwd `/home/user` y los
  repositorios entran como directorios adicionales: aportan `CLAUDE.md` y
  `.claude/rules/`, no hooks (H-DOCS-1010). `kaupamex-api/.claude/settings.json`
  declara `Stop: []`.
- **El único `Stop` activo es del lanzador.**
  `/root/.claude/launcher-settings.json` declara
  `~/.claude/stop-hook-git-check.sh`, fuera de todo repositorio: bloquea el
  cierre si hay cambios sin commitear o sin publicar. No conoce el TaskStore,
  la frontera ni las obligaciones admisibles.

Consecuencia: ningún control instalado detiene un cierre de turno por haber
trabajo admisible, y bloquear un `Stop` tampoco iniciaría una unidad —un hook
devuelve una razón al modelo, no despacha un worker—. La reactivación que
falta es la misma capacidad del Provider ya registrada (H-THYROX-682/633); el
cableado de los hooks de proyecto en una sesión remota es decisión de quien
administra el entorno (`/home/user/.claude/` o el lanzador). No se modificó
ningún hook.
