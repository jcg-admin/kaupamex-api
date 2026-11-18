# Ejecución interrumpida por reclamo del contenedor

Medido el 2026-11-18T07:13Z.

- `boot_id` al lanzar: `55781402-1bc2-4676-b39d-f619890b1e32`; tras el
  reclamo: `fbfabc36-1ade-482e-8550-1c253cafc661`, arranque
  `2026-11-18 07:09:47` UTC (lanzada a las 06:26:20: 43 min de vida).
- Al morir: en la primera prueba, la que migra desde cero, sin líneas `E`
  en el log. Sin `record.json`. Sólo existía la base de arranque
  (`orm_bootstrap_acc24adc1f62`, 45 MB); las dos de empresa no se habían
  creado, así que no quedaba estado de empresa que inspeccionar.
- PostgreSQL no volvió solo; se arrancó con
  `probes/gate-procedure/ensure-postgres.sh`. `--reclaim` retiró la base
  de arranque, sin rechazos (`reclaimed.json`); se retiró el worktree.

Es el tercer reclamo de la sesión del 2026-11-18 (01:16, 03:07, 07:09) y
el segundo que mata una ejecución en curso. Ninguna F3 de esta sesión ha
durado lo que tarda una completa (2:28 a 2:50 en las dos últimas).
