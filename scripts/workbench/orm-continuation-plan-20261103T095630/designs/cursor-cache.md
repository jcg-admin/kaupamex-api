# cursor-cache-0397 — `env.cr.cache`, la caché por cursor

Fecha: 2026-11-22T09:01:35. Prerrequisito de la etapa D-2 del plan analítico
(`get_relevant_plans` y los `create`/`write`/`_unlink_clear_cache` de
`account.analytic.applicability`, que leen y vacían `self.env.cr.cache`).

## Referencia

- `odoo19c: odoo/sql_db.py:164-174` — `BaseCursor.__init__` crea
  `self.cache = {}`.
- `odoo19c: odoo/sql_db.py:525-540` — `Cursor._close` la vacía al cerrar. Ni
  `commit` ni `rollback` la tocan: vive lo que vive el cursor.

## Estado heredado (consumidor en `cc91fbbb`)

| Contrato | Consumidor | Clase |
|---|---|---|
| `env.cr.cache` | `env.cr` es la conexión de Django (`environments.py:1096-1101`), sin `cache` | ABSENT |
| `sql_db.Cursor.cache` | portado como diccionario propio (`sql_db.py:225`, vaciado en `:454`) | SATISFIED, pero distinto del de `env.cr` |
| consumidores que la necesitan | sustitutos locales: `ContextVar` en `_export_rows` (`models.py:303`), estado por hilo en `account/decimal_precision.py:65`, `ir_fields.py:169` | DIVERGENT (sucesora) |

## Cambio previsto

1. `BaseDatabaseWrapper.cache` como propiedad perezosa: el diccionario de la
   conexión, el mismo patrón con que `cr.transaction` cuelga de ella
   (`environments.py:603-626`).
2. El corte `close` ya existente (`_wrap_cursor_cut`) descarta también la
   caché: el cursor muere y su caché con él. `commit`, `rollback` y
   `savepoint_rollback` no la tocan, como en la fuente.
3. `sql_db.Cursor.cache` deja de ser un diccionario aparte y es el de su
   conexión, así que `Environment(cr.alias, ...).cr.cache` y `cr.cache` son
   el mismo objeto.

Los sustitutos locales (`ContextVar`, estado por hilo) no se cambian aquí:
sucesora **`cursor-cache-consumers-0397`**.

## Símbolos, referencia y prueba

Prueba: `tests/unit/orm/test_cursor_cache.py`.

| Símbolo | Referencia |
|---|---|
| `_connection_cache` (`BaseDatabaseWrapper.cache`) | `odoo19c: odoo/sql_db.py:164-174` |
| `_wrap_cursor_cut` (corte `close`) | `odoo19c: odoo/sql_db.py:525-540` |
| `Cursor.cache` | `odoo19c: odoo/sql_db.py:164-174` |

## Casos de prueba

- `env.cr.cache` es un diccionario y la misma instancia en dos lecturas;
- sobrevive a `commit` y a `rollback`;
- `close` la descarta: la siguiente lectura es otro diccionario vacío;
- `sql_db.Cursor(...).cache` es la de su conexión.
