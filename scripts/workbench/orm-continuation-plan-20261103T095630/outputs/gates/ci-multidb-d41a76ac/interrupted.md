# Ejecución interrumpida por reclamo del contenedor

Medido el 2026-11-17T02:41:44.

- `boot_id` al lanzar: `168c02a4-7c8c-40d6-84bb-63c6a39f4d86`; tras el
  reclamo: `8b914808-e597-41a0-b521-7dfc43c00dda`, arranque
  `2026-11-17 02:38:56` UTC (el anterior fue `2026-11-16 23:21:31`: 3 h
  17 min entre los dos).
- Al morir: 1 passed, aprovisionando la primera base de empresa, sin líneas
  `E` en el log. Sin `record.json`.
- El último latido del `Monitor`, `02:37:19`, llegó 1 min 37 s antes del
  arranque nuevo: segunda observación contra la hipótesis de que un
  `Monitor` que emite evita el reclamo.
- PostgreSQL no volvió solo (`Removed stale pid file`). `--reclaim` retiró
  `orm_bootstrap_845062b7972f` y `company_280633641700120_db`, sin
  rechazos (`reclaimed.json`).

**Lo que se perdió por el orden.** Con el gate ya muerto, leer la base de
empresa no competía con nada, y habría dicho si el socio raíz ya tenía su
`commercial_partner_id` cuando murió. Se ejecutó `--reclaim` primero y esa
evidencia se borró. En adelante: inspeccionar las bases de una ejecución
muerta antes de reclamarlas.
