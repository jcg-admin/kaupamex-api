# Registro de intención de las bases de ci-multidb y su recuperación

Creado: 2026-11-13T05:31:31 (UTC). TASK-API-0496 (etapa local del gate multidb, dueña de
`scripts/run_multidb_isolation.py`); la cumple la obligación abierta de
`outputs/residual-databases-20261109.md`.

## Problema medido

Un reclamo del contenedor mata la ejecución antes de `drop_created`. Sus
bases (`orm_bootstrap_<hex>` y la pareja `company_<A>_db`/`company_<A+1>_db`)
quedan sin traza de procedencia: el 2026-11-09 tres, el 2026-11-13 una más
(`company_122020071908891_db`, ejecución `clone` de `3342b8b2`) y una
`orm_bootstrap_*` sin identificar. Cada vez la conciliación es manual y
termina en «no demostrado».

## Decisión

1. El ejecutor elige `MULTIDB_COMPANY_A_ID` (48 bits, como la prueba) y lo
   pasa por entorno; la prueba lo usa si está declarado.
2. **Antes** de crear nada escribe `<out>/intent.json`: base de arranque,
   las dos bases de empresa, rol dueño, revisión, `boot_id` y hora.
3. Al terminar, `record.json` como hoy.
4. `run_multidb_isolation.py --reclaim <dir>...`: por cada directorio con
   `intent.json` y sin `record.json` (ejecución interrumpida), retira cada
   base nombrada que exista, sea del rol y no tenga sesiones; escribe
   `<dir>/reclaimed.json`. Nada que no esté en un `intent.json` se toca.

Lo previo al registro sigue pendiente de conciliación en
`outputs/residual-databases-20261109.md`.

## Pruebas

- `intent.json` existe y nombra las tres bases antes del primer
  `CREATE DATABASE` (orden verificado con un doble del catálogo).
- `--reclaim` retira sólo lo nombrado, rehúsa una base de otro dueño o con
  sesiones, y no toca un directorio con `record.json`.
- Anulación: sin el registro previo, `--reclaim` no puede retirar nada.
