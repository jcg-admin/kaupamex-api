# Unidad de trabajo del ORM: `Registry.cursor()` con transacción propia

Creado: 2026-11-12T10:33:11 (UTC). TASK-API-0485, ítem del plan
`registry-cursor-unit-of-work-0485`. Referencia: odoo-tools `abe4040ec1`,
Odoo 19 Community. Continúa `environment-ownership-contract.md` §5.

## Por qué existe

La suite del lote 3 mostró un `default_env` que sobrevivía al rollback de
una prueba y volcaba con un `write_uid` inexistente. La corrección de
`tests/conftest.py` (`release_test_transaction`) aísla las pruebas, pero **no
es la garantía del núcleo**. La pregunta es si la misma fuga ocurre fuera de
pytest. Medido: sí, en todo proceso que reutilice la conexión entre unidades
de trabajo.

## El contrato de la fuente

| Pieza | Comportamiento | Cita |
|---|---|---|
| `Registry.cursor(readonly=False)` | devuelve un cursor **nuevo** sobre una conexión del pool | `odoo/orm/registry.py:1165-1186` |
| `BaseCursor.transaction` | nace `None`; la crea el primer `Environment(cr, ...)` | `odoo/sql_db.py:160-174`, `odoo/orm/environments.py:70-72` |
| `Transaction.default_env` | el primer entorno con uid entero sobre ese cursor | `environments.py:558`, `:86-89` |
| `with cr:` | `commit()` si no hubo excepción; `close()` siempre | `sql_db.py:228-245` |
| `commit()` | `flush()` (vuelca como `default_env`), COMMIT, `clear()` | `sql_db.py:560-568` |
| `rollback()` | `clear()`, ROLLBACK | `sql_db.py:570-576` |
| `close()` / `_close()` | vacía la caché, revierte lo no confirmado y devuelve la conexión; la transacción muere con el cursor | `sql_db.py:524-558` |
| cron | un cursor por trabajo: `with cls.pool.cursor() as job_cr:` y `api.Environment(job_cr, job['user_id'], ...)` | `odoo/addons/base/models/ir_cron.py:480-486` |
| HTTP | un cursor por petición desde el registro | `odoo/http.py:2283`, `:2319` |

Por construcción, en la fuente un `default_env` no puede cruzar de una unidad
de trabajo a otra: cada una tiene su cursor y la transacción del ORM cuelga
de él.

## El mecanismo de este árbol, medido

1. **Quién crea `default_env`.** `Environment.__new__` lo fija en la
   transacción si aún no hay uno y el uid es entero
   (`src/orm/environments.py`, `__new__`).
2. **Dónde vive.** En la `Transaction` colgada de la conexión de Django
   (`orm_transaction`); una por alias y por hilo.
3. **Quién lo posee.** La conexión del alias, no la unidad de trabajo.
4. **Restauración del entorno activo.** `Environment.__exit__` devuelve los
   `ContextVar` en orden LIFO; eso restaura el **canal**, no la transacción.
5. **Al terminar una operación.** Nada: la transacción sigue en la conexión.
6. **Tras un rollback.** El corte `rollback`/`savepoint_rollback` llama a
   `clear()`: vacía caché, marcas y colas, y **conserva `envs` y
   `default_env`**, igual que la fuente sobre un cursor vivo.
7. **Tras una excepción.** Lo mismo que 6 si alguien revierte; si no, nada.
8. **Entornos anidados.** Comparten la transacción del alias; el primero con
   uid fija `default_env` para todos.
9. **Reutilización de la conexión.** El corte `close` descarta la
   transacción. Con `CONN_MAX_AGE` 0 (valor por omisión de Django; `base.py`
   no lo declara) `close_old_connections`, conectado a `request_started` y
   `request_finished` (`django/db/__init__.py:57-63`), cierra la conexión al
   final de cada petición (`close_if_unusable_or_obsolete`,
   `django/db/backends/base/base.py:591-614`), así que **en HTTP** la
   transacción muere con la petición. Es una afirmación por mecanismo; su
   prueba está en la tabla de controles.
10. **Fuera del ciclo HTTP.** El cron (`IrCron._run_job`) corre cada trabajo
    con `user_scope(...)` sobre la **misma conexión** y declara la
    divergencia («la fuente abre un cursor propio… Sucesor: tarea #42», un
    ordinal efímero). `Registry.cursor()` devuelve un cursor DB-API de la
    conexión compartida (`src/orm/registry.py:2659-2686`). Resultado: en un
    proceso de larga vida, el `default_env`, la caché y las colas de un
    trabajo pasan al siguiente, y el COMMIT de un trabajo confirma también lo
    del planificador.

## La corrección: TRAE / CONSTRUYE

Django **trae** varias conexiones simultáneas por alias (`ConnectionHandler`)
y el ciclo `commit`/`rollback`/`close` con sus cortes ya cableados a la
transacción del ORM. Falta **construir** el cursor de la fuente sobre eso:

- `Registry.cursor()` registra un alias efímero `<alias>__cursor_<n>` con la
  configuración del alias del registro y devuelve un `Cursor` que posee esa
  conexión: `execute`/`fetch*`/`dictfetch*` delegan en un cursor DB-API;
  `commit`, `rollback` y `close` llaman a los de la conexión (con lo que los
  cortes vuelcan, vacían y descartan la transacción del ORM); `close` retira
  el alias. `with cr:` sigue a `sql_db.py:240-245`.
- `Environment(cr.alias, uid, ctx)` funciona sin cambios: el entorno ya
  nombra su cursor por alias.
- `IrCron._run_job` abre `with Registry(alias).cursor() as job_cr:` y
  `Environment(job_cr.alias, job.user_id, {...})` por trabajo, y retira la
  divergencia declarada.
- `readonly=True` conserva la búsqueda de réplica por alias.

## Controles (RED antes de implementar)

| Control | Qué demuestra | Anulación esperada |
|---|---|---|
| dos unidades sobre la misma conexión: la segunda vuelca con su propio usuario, no con el `default_env` de la primera | la fuga fuera de pytest, sin depender del orden de las pruebas | sin cursor propio, `write_uid` es el de la primera |
| `with registry.cursor()` confirma su trabajo sin confirmar el del llamador | COMMIT acotado a su conexión | sin conexión propia, el rollback del llamador se lleva el trabajo |
| excepción dentro de `with cr:`: revierte y cierra; la transacción del ORM se descarta | `sql_db.py:240-245` | sin `close` la transacción sigue viva |
| el alias efímero desaparece al cerrar | sin fuga de conexiones | — |
| HTTP: `close_if_unusable_or_obsolete` con `CONN_MAX_AGE` 0 descarta la transacción | la afirmación 9 | sin el corte `close`, el `default_env` sobrevive |
| cron: dos trabajos de usuarios distintos fechan `write_uid` con el suyo | el consumidor real | con `user_scope` sobre la conexión compartida falla |

## Lo que esta unidad no cierra

- La réplica de sólo lectura (`<alias>_readonly`) sigue sin declararse en
  `DATABASES`; el camino es el de escritura, como en la fuente sin réplica.
- `ir_actions.py:2472` y los usos de `Registry.cursor()` en
  `registry.py:2002,2492` se revisan contra el nuevo contrato en el mismo
  pase; si alguno necesita la conexión compartida, se declara con su razón.
