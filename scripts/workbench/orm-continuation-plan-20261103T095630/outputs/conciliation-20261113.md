# Conciliación de recursos, TASK, plan e inventario — 2026-11-13

Cerrado: 2026-11-13T05:49:11 (UTC). Revisión publicada de partida: `92136570`.

## 1. Recursos y reservas

| Recurso | Medido | Fuente |
|---|---|---|
| Disco | 1,15-1,2 GB libres (98 %) | `df -B1 /` |
| Reservas de disco vigentes | ninguna: `/home/user/thyrox/.claude/cache/disk-admission.json` no existe (cada ejecución suelta la suya) | lectura del ledger |
| Admisión real | ci-multidb 380 MB + piso 300 MB = 680 MB; suite 200 + 300 = 500 MB; ambas caben | `run-gate-multidb-staged.sh`, `full-batch.sh` |
| Worktrees propios | 0 (los de ejecuciones terminadas, retirados tras persistir su evidencia) | `git worktree list` |
| PostgreSQL | ≈1,3 GB en 24 bases | `pg_database_size` |
| Cachés | `/root/.cache/uv` 738 MB, `pip` 111 MB — no se tocan: el `.venv` puede compartir inodos | `du` |

## 2. Riesgos corregidos

- **Arranque tras reinicio:** el cluster quedaba parado y se arrancaba a mano.
  `probes/gate-procedure/ensure-postgres.sh` lo hace idempotente y lo
  invocan los dos lanzadores (`2a3f1a74`).
- **Restos de ejecuciones interrumpidas:** `run_multidb_isolation.py` escribe
  `intent.json` antes del primer `CREATE DATABASE`; `--reclaim` retira
  sólo lo declarado por una ejecución sin `record.json` (`2a3f1a74`).
- **Pendientes de conciliación, no borrados** (propiedad no demostrable, anteriores
  al registro): `orm_bootstrap_12769386391b`, `orm_bootstrap_276bbe3da956`,
  `orm_bootstrap_b42418e0a4d4`, `company_122020071908891_db`,
  `company_11710386656870_db`, `company_11710386656871_db`,
  `company_201103761692838_db`, `company_201103761692839_db`, y las
  familias `orm_x2hokp_t41_*`, `orm_x2hokp_dev*`, `orm_x2hokp_preserve`,
  `orm_x2hokp_probe`, `orm_refproc_*`. Continúa
  `residual-databases-20261109.md`.

## 3. Estado canónico de las tres unidades

Fuente: TaskStore en sólo lectura (`immutable=1`); `plan.jsonl`;
`continuation.jsonl` (`settle_item.py`).

| Unidad | TASK canónica | Fila propia en TaskStore | Plan | Asentada (`settle_item`) | Commits | Verificación |
|---|---|---|---|---|---|---|
| `request-unit-of-work-0485` | TASK-API-0485 (`in_progress`) | **no** | sí (`fe9a477e`) | sí, `fe9a477e` | `7fa471df` | suite `full-uow2-47b60765`; ci-multidb `3342b8b2` provision y clone |
| `request-unit-of-work-integrity-0485` | TASK-API-0485 | **no** | sí | **no** (pendiente) | — | — |
| `bulk-delete-invalidation-0485` | TASK-API-0485 | **no** | sí | sí, `47e251da` | `332c2b41` | suite `full-seed2-d10ae3ad`; ci-multidb `3342b8b2` |
| `multidb-gate-clone` | TASK-API-0496 (`completed` en el TaskStore) | **no** | sí | sí, `47e251da` | `fd324cca`, `945d6680` | ci-multidb `3342b8b2` clone conforme |

Relación: las tres son **unidades derivadas** de su TASK, registradas en el
plan del banco; **ninguna** tiene fila propia en el TaskStore, y
`TASK-API-0496` figura `completed` aunque recibió trabajo posterior
(`multidb-gate-clone`, `multidb-run-intent-0496`). No se escribe en el
TaskStore desde esta VM: reabrir `TASK-API-0496` o crear una TASK para
estas unidades queda **pendiente de autoridad**.

Aceptación: ninguna; requiere al ejecutor (I-011, `plan_coverage.json`).

## 4. Plan e inventario

- `plan.jsonl`: 217 unidades; 197 asentadas; 20 pendientes.
- `plan_coverage.json`: veredicto **B**; 71 TASK abiertas; 59 sin unidad;
  17 bloqueadas; 181 asentadas y no integradas en
  `origin/feature/codex-workspace-bootstrap`.
- Obligaciones (`obligation_classification.tsv`, 2026-11-10): 1 543
  (1 151 sin verificar, 392 ausentes); 910 de TASK-API-0485.
- Contratos de `BaseModel` (`designs/timestamped-copy-contract-matrix.md`):
  de 188 nombres, 4 ausentes en todos los modelos de producción; la mayoría
  ausentes en 386 de 396 (sólo 10 de producción derivan de `BaseModel`).

## 5. Siguiente unidad iniciada

`copy-universality-0485` (`designs/copy-universality.md`): RED 3/3, GREEN,
anulación exacta 3; suite integral en curso.
