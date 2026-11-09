# Diseño — fechas de `TimeStampedModel` con la hora de la transacción

Fecha: 2026-11-09T01:22:26 · TASK-API-0485.

## Contrato (odoo19c)

- `Cursor.now()` devuelve *"the transaction's timestamp NOW() AT TIME ZONE
  'UTC'"*, consultado una vez y memorizado (`odoo/sql_db.py:271-278`).
- `create` fija `create_date` y `write_date` con `cr.now()`
  (`odoo/orm/models.py:4803-4805`); `write` fija `write_date` con
  `cr.now()` (`:4396`).
- Consecuencia: todo lo creado o escrito en una misma transacción lleva la
  misma fecha, y un `write` en la transacción del `create` no mueve
  `write_date`.

## Aquí (medido en el código)

`TimeStampedModel` (`src/addons/base/models/timestamped_mixin.py`) declara
`created_at = DateTimeField(auto_now_add=True)` y
`updated_at = DateTimeField(auto_now=True)`: Django fija la hora de cada
`pre_save` (`timezone.now()`), distinta en cada guardado de la misma
transacción. No existe porte de `cr.now()` (`grep -rn "def now(self" src` → 0).

## Casos (prueba `tests/unit/orm/test_timestamped_transaction_now.py`)

| Caso | Esperado |
|---|---|
| dentro de un `atomic`, crear y luego escribir | `updated_at == created_at` |
| dentro de un `atomic`, dos altas | misma `created_at` |
| la fecha es la de PostgreSQL `now()` de esa transacción | igual a `SELECT now()` |

## Corrección propuesta

Un `transaction_now()` que memorice `SELECT now()` por transacción de la
conexión (equivalente de `cr.now()`), y que los dos campos de
`TimeStampedModel` lo usen en su `pre_save` en vez de `timezone.now()`.
La memoria se invalida al cerrar la transacción (`on_commit`/rollback):
hay que medir dónde engancharlo sin crear un segundo mecanismo si
`orm.environments` ya tiene el ciclo de vida de la transacción.

## RED medido

Los tres casos fallan: en una misma transacción `updated_at` avanza 15 ms
tras el `create`, dos altas difieren en 14 ms, y la fecha no es la de
`SELECT now()`.

## Riesgo a medir con la suite

Bajo `pytest-django` cada prueba es una transacción: con la corrección, sus
filas comparten fecha. Cualquier prueba o código que ordene por `created_at`
y espere el orden de alta (`get_latest_by = 'created_at'`) quedará con
empates. La referencia tiene el mismo comportamiento y ordena por `id`
cuando necesita el orden de alta.
