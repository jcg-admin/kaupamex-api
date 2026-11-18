# `Environment.execute_query` vuelca lo que la consulta declara

Fecha: 2026-11-18T07:32:28. Unidad: `employee-map-display-cost-0241`
(bloquea el paso H2). Clase A: contamina toda lectura agregada de un
calculado almacenado pendiente.

## Lo medido

Con un calendario recién creado y sus tramos, dentro de la misma
transacción:

| Lectura | `hours_per_day` |
|---|---|
| ORM (`calendar.hours_per_day`) | 8.0 |
| `_read_group([('id','in',[id])], ['hours_per_day'], ['id:array_agg'])` | 0.0 |
| SQL directo, antes y después del `_read_group` | 0.0 |

El `_read_group` lee la columna sin calcular el valor pendiente.

## La fuente

`odoo19c: odoo/orm/environments.py:527-535` — `Environment.execute_query`:
*"The method automatically flushes all the fields in the metadata of the
query"*; su primera línea es `self.flush_query(query)` (`:515-525`). Lo
mismo `execute_query_dict` (`:537-…`). Los campos los declara el `SQL` al
componerse (`to_flush=self` en `Field._field_to_sql`).

## Aquí

- `SQL(..., to_flush=...)` existe (`src/tools/sql.py:219`, `:337`) y
  `Field._field_to_sql` lo declara (`src/orm/fields.py:766`).
- `Environment.flush_query` existe y está probado
  (`tests/unit/orm/test_environments_pooling_and_flush.py:345`).
- `Environment.execute_query` (`src/orm/environments.py:1626`) delega en
  la función de módulo `execute_query`, cuyo docstring dice que *"el
  `flush_query` de la fuente no tiene contraparte porque el ORM de Django no
  difiere escrituras a un caché propio"*. Esa premisa es falsa desde que
  existe la cola de cómputos: la tabla de arriba la refuta.
- `Environment.execute_query_dict` tampoco vuelca.

## El cambio

1. `Environment.execute_query` y `Environment.execute_query_dict` llaman a
   `self.flush_query(query)` antes de ejecutar, como la fuente.
2. La función de módulo `execute_query(query, using)` no cambia: no tiene
   entorno con que volcar y la usan `tools/query.py` y quienes no tienen
   `env`. Su docstring corrige la premisa.

## Prueba

`tests/unit/orm/test_execute_query_flushes.py`:

| Caso | Espera |
|---|---|
| un calculado almacenado pendiente, leído por `env.execute_query` con un `SQL` que lo declara en `to_flush` | la consulta devuelve el valor calculado |
| ídem por `env.execute_query_dict` | ídem |
| `_read_group` sobre `hours_per_day` de un calendario recién creado | 8.0 |

Anulación: sin la llamada a `flush_query` caen los tres casos, y ninguno
de `test_environments_pooling_and_flush.py`.

## Radio

Transversal: toda consulta de `_read_group`, `_search` con bloqueo, y los
cinco usos de `models.py` pasan por aquí. Se ejecuta la suite completa
(F2) antes de asentar.

*Métrica:* valor devuelto por la consulta frente al valor de la caché.
*Ciega a:* el coste del volcado añadido en consultas calientes.
