# Equivalencia de `IN` contra `= ANY` y `IN (SELECT unnest)` en PostgreSQL

Resultado medido en PostgreSQL 16.15 con psycopg 3.3.4 (`outputs/result.json`):

- `col = ANY(%s)` con una lista coincide con `col IN (v1, ..., vn)` en las 22
  comparaciones, incluidos los NULL (verdad de tres estados) y los duplicados.
- `col IN (SELECT unnest(%s))` coincide para listas de enteros con algún valor
  no nulo (10 de 10) y **falla** con `AmbiguousFunction: function
  unnest(unknown) is not unique` para listas de texto y para `[None]`:
  psycopg 3 envía esos arreglos como `unknown`.

`Query._ids` sólo contiene ids de registro enteros, así que dentro del dominio
de `Query` las dos formas son equivalentes; fuera de él no lo son.

TASK-API-0495.
