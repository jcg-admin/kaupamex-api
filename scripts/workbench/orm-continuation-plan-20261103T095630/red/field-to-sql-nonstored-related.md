# RED, GREEN y controles — `_field_to_sql` sobre un `related` no almacenado

Comando: `uv run pytest tests/unit/orm/test_field_to_sql_related.py -q --reuse-db -p no:cacheprovider -W ignore`

## RED

3 failed, 1 passed: `ValueError: Invalid field 'foo_name' on model
'test_orm.TestOrmRelated'` (y `foo_bar_name`). Pasa el control negativo
(`category.depth`, calculado sin `related`).

## GREEN — dos causas, no una

1. `_field_to_sql` rechazaba `not concrete` antes de la rama del `related` no
   almacenado. Se adelanta la rama; el rechazo queda para el resto.
2. Al adelantarla apareció la segunda: `_traverse_related_sql` recorría sobre
   la **clase** (`model = type(self)`) y `Many2one.join` llama a
   `model._field_to_sql(...)`, que sobre una clase desplaza los argumentos
   (`AttributeError: 'Query' object has no attribute 'find'`). En la fuente el
   recorrido va sobre recordsets: ahora empieza en `self` y cada salto sigue
   sobre el recordset vacío del comodelo (`_from_ids(env, (), ())`, o una
   instancia si no es `BaseModel`). Devuelve lo mismo que la fuente:
   `(recordset, campo, alias)`.

24 passed con `test_fields_map_contract.py`, `test_order_to_sql.py` y
`test_related_traversal_access.py`.

## Controles de anulación

| Anulación | Caen |
|---|---|
| rechazo `not concrete` delante de la rama | 3: un salto, dos saltos, orden |
| recorrido sobre la clase | 3: los mismos |

El control negativo (`depth`) sobrevive a los dos. Admisión de estilo: PASS.

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `FieldSqlMixin._field_to_sql`, `FieldSqlMixin._traverse_related_sql`. |
| Changed behavior | Un `related` no almacenado se convierte a SQL con sus JOIN; antes lanzaba `ValueError`. `_traverse_related_sql` devuelve un recordset, no una clase. |
| Direct consumers | Todo `_field_to_sql`: dominios (`condition_to_sql`), propiedades, relaciones, `_order_field_to_sql`, `fields_misc`. |
| Indirect consumers | Búsquedas y órdenes por un `related` no almacenado, que antes fallaban. |
| Required contract tests | `tests/unit/orm/test_field_to_sql_related.py`. |
| Required regression tests | Directorios con `_field_to_sql`, `_traverse_related_sql`, `condition_to_sql`, `related=` o búsquedas: 18 directorios de `tests/`. |
| Required integration gates | Suite completa y multidb en el corte: transversal. |
| Previously valid evidence | Ninguna para esta revisión. |
| Uncovered risks | Un consumidor que dependiera de que `_traverse_related_sql` devolviera la clase: un solo llamador (`_field_to_sql`). |
