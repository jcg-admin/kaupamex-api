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

## Cadena medida y punto de inserción (2026-11-12T18:29:17 UTC)

`MIDDLEWARE` (`src/config/settings/base.py`), en orden: Security,
CorrelationId, CookieGovernance, Cors, Session, Common, Csrf, Authentication,
CheckIdentity, **CompanyContext**, DeviceLog, Messages, XFrame, UtmCookie.
`CompanyContextMiddleware` (`src/addons/base/models/ir_http.py:330`) fija el
`ContextVar` de empresa desde `request.user.company_id`; el router elige con
él la base de la petición. La unidad de trabajo va **justo después**: antes no
se sabe qué base abrir, y después todo lo que escriba la vista ya tiene base.

Lo que el árbol ya trae y la unidad reutiliza:

- `_CURSOR_CUTS` (`src/orm/environments.py`): el `commit` de la conexión
  vuelca la transacción del ORM y luego la vacía (≙ `sql_db.py:560-564`), el
  `rollback` la vacía. Con un `transaction.atomic` por petición, su salida
  correcta llama a `commit()` y el volcado ocurre en el momento de la fuente,
  sin un `flush` propio del middleware.
- `registry_for_alias`/`active_registry` (`c89eed08`): el registro de la
  base de la petición, con su `cache_invalidated`.

Lo que hoy falta, y por qué la unidad no duplica commits: en autocommit Django
no llama a `commit()`, así que el corte no ocurre y lo pendiente del ORM
queda a merced del siguiente volcado explícito. El `atomic` de la unidad es
el único `COMMIT` de la petición; los `atomic` de las vistas pasan a ser
savepoints (`DATABASES[...]['ATOMIC_REQUESTS']` no se activa, para no tener
dos mecanismos que abren la misma transacción).

Fuera de HTTP: el cron ya tiene su cursor por trabajo (`7f56d1dd`); los
comandos de gestión y las migraciones no pasan por el middleware y se tratan
aparte (`migrate` corre en su propia transacción por migración, como la
instalación de la fuente).

## Cuándo revierte la unidad (2026-11-12T18:29:52 UTC)

En la fuente revierte **toda excepción** del despacho (`retrying`,
`odoo/service/model.py:192-235`). Aquí la vista no propaga la excepción al
middleware: Django la convierte en respuesta dentro de la cadena, y DRF la
maneja y devuelve una `Response` con `response.exception = True`
(`rest_framework/views.py:477`). Su `set_rollback` (`:66-69`) sólo actúa
sobre bases con `ATOMIC_REQUESTS`, que aquí no se activa (abriría una
transacción en **cada** alias instalado, una por empresa).

Por eso la unidad decide así, sobre el alias de la petición:

| Señal | Origen | Desenlace |
|---|---|---|
| `process_exception` recibió una excepción | Django, vista no DRF | rollback + `reset_changes()` |
| `response.exception` es verdadero | DRF manejó una excepción | rollback + `reset_changes()` |
| ninguna | respuesta normal (incluido un 4xx devuelto a propósito) | COMMIT (vuelca por `_CURSOR_CUTS`) + `signal_changes()` |

Reintento: si la excepción es `SerializationFailure`, `DeadlockDetected` o
`LockNotAvailable` de psycopg, se revierte, se llama a `reset_changes()` y se
vuelve a servir hasta 5 veces con espera `uniform(0, 2**intento)`, salvo que
la petición traiga archivos que no se puedan rebobinar (la fuente rehúsa igual,
`model.py:197-206`). La traducción de `IntegrityError` a `ValidationError`
(`model.py:207-214`) va en la misma unidad, como el 400 de DRF.

## RED

1. vista que escribe y responde bien → la fila queda, `signal_changes` una vez,
   `reset_changes` cero;
2. vista que escribe y lanza → la fila no queda, `reset_changes` una vez,
   `signal_changes` cero;
3. vista DRF que escribe y lanza `ValidationError` → igual que 2;
4. `check_signaling` se llama antes de servir;
5. una `SerializationFailure` en el primer intento → segundo intento confirma;
6. lo pendiente del ORM se vuelca antes del COMMIT (un cómputo almacenado
   marcado en la vista llega a la fila).
