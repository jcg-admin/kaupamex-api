# Una unidad de trabajo por petición: COMMIT, señal y reversión

Creado: 2026-11-12T14:06:24 (UTC). TASK-API-0485. Unidad `request-unit-of-work-0485`.
Une dos fronteras medidas: nadie llama a `Registry.signal_changes` ni a
`reset_changes` (`designs/registry-caches-per-database.md`), y la hora de
transacción del CRM no coincide en autocommit
(`designs/crm-transaction-time-shared-read.md`).

## Contrato de la fuente

| Pieza | Fuente | Qué hace |
|---|---|---|
| despacho HTTP con base | `odoo/http.py:2267-2335` (`_serve_db`) | abre `registry.cursor(readonly=True)`, `registry.check_signaling(cr)`, y sirve con `service_model.retrying(serve_func, env=self.env)`; una ruta de escritura usa un cursor de lectura/escritura |
| RPC | `odoo/service/model.py:131-138` | `with registry.cursor() as cr`; al terminar `registry.signal_changes()`, al fallar `registry.reset_changes()` |
| `retrying` | `odoo/service/model.py:160-240` | llama, vuelca (`cr.flush()`); ante `IntegrityError`/`OperationalError`/`ConcurrencyError` revierte, `transaction.reset()`, `reset_changes()` y reintenta hasta `MAX_TRIES_ON_CONCURRENCY_FAILURE = 5` (`:30`) con espera aleatoria `uniform(0, 2**intento)`; un `IntegrityError` se traduce a `ValidationError` con `_sql_error_to_message`; ante cualquier otra excepción `transaction.reset()` + `reset_changes()`; si sale bien, `cr.commit()` y `signal_changes()` |
| cron | `ir_cron.py:480-486` | un cursor por trabajo (ya portado en `7f56d1dd`) |

## Lo que hay aquí (medido)

- `src/config/settings/base.py` no declara `ATOMIC_REQUESTS` (0 apariciones
  en `src/config/settings/*.py`): una vista de DRF corre en autocommit, y
  cada sentencia es su propia transacción.
- `MIDDLEWARE` (`base.py:182-...`) no tiene una capa de unidad de trabajo.
- `signal_changes`/`reset_changes` sólo se llaman desde `manage_changes`,
  que nadie usa; `check_signaling` tampoco tiene llamador por petición.

## Diseño

Un middleware `UnitOfWorkMiddleware` (en `addons/base/models/ir_http.py`,
junto a `CorrelationIdMiddleware`, después de `AuthenticationMiddleware`):

1. resuelve el registro de la base de la petición (`registry_for_alias` del
   alias que el router elige) y llama `check_signaling()`;
2. sirve la vista con el equivalente de `retrying`: `transaction.atomic`
   sobre ese alias, volcado del entorno al final del bloque, reintento ante
   `SerializationFailure`/`DeadlockDetected`/`LockNotAvailable` de psycopg
   con la misma espera, traducción de `IntegrityError` a `ValidationError`;
3. al salir bien, `signal_changes()`; ante excepción, `reset_changes()` y
   descarte de la transacción del ORM.

Riesgos que el diseño tiene que medir antes de RED:

- **reintento de una petición**: sólo es seguro si la vista no tuvo efectos
  fuera de la base (correo, HTTP saliente); la fuente rebobina los archivos y
  rehúsa si no puede (`model.py:197-206`). Se porta igual.
- **respuestas en streaming** (`StreamingHttpResponse`/`FileResponse`): el
  cuerpo se genera fuera del `atomic`; la fuente las sirve en el mismo
  cursor. Medir qué vistas las usan.
- **vistas con `atomic` propio** (p. ej. `CartItem`, `base.py:717`):
  quedan anidadas como savepoint; mismo efecto que en la fuente.
- **base de la petición**: el alias lo decide el router por empresa
  (`orm/routers.py`); una petición que toque dos bases abriría dos unidades,
  y la fuente no lo permite: se rehúsa con error declarado.

## Pruebas (RED)

- una vista que invalida una caché señaliza al terminar (fila nueva en
  `orm_signaling_default`) y no señaliza si falla;
- una vista que falla tras escribir no deja la fila (rollback de la unidad);
- un `crm.lead` creado por la API tiene `date_open == create_date ==
  date_last_stage_update`;
- un conflicto de serialización se reintenta y la segunda vez confirma;
- un `IntegrityError` llega como 400 con el mensaje de
  `_sql_error_to_message`.

## Medición de los riesgos (2026-11-12T14:06:41 UTC)

*Métrica:* archivos de `src/` y `addons/` con `StreamingHttpResponse` o
`FileResponse` (7: `service/db.py`, `base/models/ir_binary.py`,
`config/urls.py`, `auto_backup/controllers/main.py`,
`web/controllers/{database,webmanifest,binary}.py`) y archivos de vistas o
controladores con `transaction.atomic` (17). *Ciega a:* respuestas que
generan el cuerpo de forma perezosa sin esas clases y a `atomic` envuelto en
un helper con otro nombre.

Las siete de streaming sirven binarios y respaldos: la unidad las cierra antes
de devolver la respuesta, y su generador no puede escribir en la base. Las 17
con `atomic` propio quedan como savepoints dentro de la unidad.
