# Clasificación de los 12 commits locales de Thyrox (rama `claude/bold-fermat-x2hokp`)

Coordinación, no condición de cierre de `completar-raiz-orm`. Medido con
`git log`, `git show --stat`, `git patch-id --stable`, `git branch -r
--contains` y la `VERIFICATION.md` que la autoridad publicó en
`origin/integrate/x2hokp-local-plan-supply` (commit `1e26c8c57`).

Autoría de los 12: `Nestor Monroy` / committer `jcg-admin`; procedencia:
esta sesión (VM-x2hokp, `session_01A97MaC4ct1CksvJt5UG3cj`). Ninguno está
en una rama remota con el mismo SHA.

## Commits de código (3) — ya transferidos y superados

| SHA | Fecha | TASK | Archivos | Equivalente publicado |
|---|---|---|---|---|
| `ebc45a959` | 2026-11-04 | TASK-THYROX-1112 | `src/session/node_next_task.py`, `task_continuation.py`, su prueba | `395fb00ec` en `origin/integrate/x2hokp-local-plan-supply` |
| `f2b9d588c` | 2026-11-04 | TASK-THYROX-1033 | `src/session/local_plan.py` (`incorporate_plan_rows`), su prueba | `f01e2eb2a`, misma rama |
| `a62eca38b` | 2026-11-04 | (sin `Refs`; continúa TASK-THYROX-1033) | `src/session/local_plan.py` (`supply_plan`), su prueba | `e60eec666`, misma rama |

- Dependencias: lineales, `ebc45a959` → `f2b9d588c` → `a62eca38b`.
- `patch-id` distinto del equivalente porque la autoridad los aplicó desde
  texto transcrito y normalizado; su `VERIFICATION.md` declara los
  `patch-id` del remitente iguales a los de la copia normalizada.
- La autoridad añadió encima `030b57de0` (cerrojo del plan: sin él, 3 de
  10 ejecuciones de `supply` correctas; con él, 10 de 10) y `8255c252d`
  (completar la procedencia de una incorporación que murió a medias). La
  versión local **no tiene** esas dos correcciones.
- Pruebas en el HEAD local, esta sesión: `test_local_plan` 22 ok, 0 fallos;
  `test_task_continuation_node` 15 ok, 0 fallos.
- Integración: `origin/integrate/x2hokp-local-plan-supply` **no** es
  ancestro de `origin/develop` (`git merge-base --is-ancestor`).

### El cambio que incorpora unidades al plan del Consumer

Corrige una deficiencia genérica del Provider: `task_continuation` no crea
trabajo y `local_plan` reescribía `plan.jsonl` entero aceptando sólo citas
`TASK-THYROX` con rutas del Provider, así que un Consumer cuya frontera se
agotaba no tenía vía admitida para añadir una unidad. `incorporate_plan_rows`
añade sin reescribir, rehúsa un id repetido (idempotencia por id) y una TASK
cerrada, y resuelve `owned` y la prueba de `verify` contra el árbol del
Consumer (aislamiento). `supply_plan` respeta los claims ajenos y las
dependencias no aceptadas. Su defecto, medido por la autoridad, es la
carrera entre dos escritores: lo corrige `030b57de0`, que sólo existe en
la rama de integración.

Efecto sobre esta sesión: las nueve liquidaciones usaron la versión local,
con un solo escritor por plan; la carrera no aplica a ese uso, pero
publicar la versión local reintroduciría el defecto ya corregido.

**Decisión de esta sesión: conservar los 3 SHA en local, no publicarlos.**
La versión correcta ya está publicada por la autoridad; integrarla en
`develop` es decisión de VM-A.

## Commits de datos (9) — bajo custodia de esta sesión

`03730be0a`, `a0e4598e9`, `e42b5521d`, `51d3ae43f`, `b10c96b75`,
`717e0b176` (la `VERIFICATION.md` los nombra: «siguen en su custodia: no
se transfirieron»), y los posteriores `89fd50062`, `f440d1bb6` y
`b9bca0061`. Sólo tocan `agent-results/agent_store.sqlite3` (filas de
hallazgos indexados y citas `TASK-*` acuñadas por la interfaz autorizada
`bin/agent_store` / `bin/task_ids`). No tocan `src`, `tests` ni `bin`.

Riesgo de publicarlos: el store es un binario; dos ramas que lo modifican
no se fusionan por contenido, y publicarlo sin la autoridad podría pisar
filas de otra sesión. No hay autorización vigente para publicar el store
de esta rama: **se conservan los SHA y se pide la decisión a VM-A**.
