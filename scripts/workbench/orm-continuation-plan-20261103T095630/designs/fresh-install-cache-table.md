# La tabla de caché antes de migrar

Fecha: 2026-11-11 · TASK-API-0485 (lo destapó la prueba de conservación de la
hija B).

## Defecto medido

Una base de desarrollo nueva (`config.settings.development`, `DatabaseCache`)
no termina `migrate`. Todas las migraciones se aplican, y después falla la
carga de datos que corre en `post_migrate` (`install_cycle.load_modules_after_migrate`,
diseño `module-install-cycle.md`):
`relation "cache_table" does not exist` (`outputs` del probe,
`preserve-b/migrate-C.log`).

Las tres rutas canónicas ejecutan `migrate` y **después**
`createcachetable`: `kaupamex-bin server` (`server.py`, `('migrate',
'createcachetable')`), `scripts/bootstrap.sh` (fase 5) y el `README.md`.
En una base nueva la segunda nunca llega. La suite no lo ve porque
`config.settings.testing` usa `LocMemCache`.

## Corrección

Se invierte el orden: primero `createcachetable`, luego `migrate`.
`createcachetable` no depende de las migraciones: crea la tabla de
`CACHES[...]['LOCATION']` desde la conexión, y es idempotente.

Pruebas: `test_kaupamex_bin.py` fija el orden (RED con el orden viejo). La
prueba de conservación de B migra una base nueva con `development` por la
misma ruta.
