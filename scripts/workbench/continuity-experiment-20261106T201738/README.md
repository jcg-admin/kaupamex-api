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
