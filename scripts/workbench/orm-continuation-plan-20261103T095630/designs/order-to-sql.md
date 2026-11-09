# `BaseModel._order_to_sql` y `_order_field_to_sql`

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo/orm/models.py:5224-5322`.

## Contrato

- `_order_to_sql(order, query, alias=None, reverse=False) -> SQL`: usa
  `self._order` si `order` es falso; `SQL()` si no hay orden; valida con
  `_check_qorder`; por cada término (`regex_order`) toma dirección y nulos,
  los invierte con `reverse`, une `campo.propiedad` y delega en
  `_order_field_to_sql`; junta los términos no vacíos con `", "`.
- `_order_field_to_sql(alias, field_name, direction, nulls, query) -> SQL`:
  - campo inexistente → `ValueError("Invalid field %r on model %r")`;
  - `many2one`: guarda de ciclo en el contexto `__m2o_order_seen`; con
    `x_id.id` o comodelo ordenado por `id`, ordena por la columna y la añade a
    `query._order_groupby`; si no, antepone `IS NOT NULL`/`IS NULL` para
    `NULLS FIRST`/`NULLS LAST`, hace `field.join` (LEFT JOIN) y delega en
    `comodel._order_to_sql(coorder, query, alias=coalias, reverse=DESC)`;
  - booleano → `COALESCE(col, FALSE)`;
  - resto → `"%s %s %s"` con la columna de `_field_to_sql`, añadida a
    `query._order_groupby`.

Consumidores de la referencia: `Field._description_sortable` (`fields.py:919`),
`BaseModel._search` (`:5385`), `_read_group` (`:2197`) y los `override` de
`stock_picking`, `project_project`, `hr_job`, `account_account`, `res_device`.

## Kaupamex

- Ausentes los dos métodos (inventario: `absent`).
- Existen sus piezas: `_check_qorder` (`src/orm/models.py:3979`),
  `regex_order`, `parse_field_expr` (`orm.utils`), `_field_to_sql`
  (`:2448`), `Many2one.join` (`fields_relational.py:1458`), `Query` con
  `_order_groupby` (`tools/query.py:154`).
- `order_to_django` (`models.py:5178`) es la adaptación que hoy usa `_search`
  sobre `QuerySet`. Sigue siendo el camino de `_search`; esta unidad no lo
  cambia.

## Decisión

Portar los dos métodos verbatim sobre `Query`/`SQL` en `BaseModel`. El
contexto `__m2o_order_seen` se lleva con `with_context`, como en la fuente.

No se toca `_description_sortable` en esta unidad: su divergencia de mecanismo
está declarada y cambiarla altera la descripción de campos que consume `web`;
será su propia unidad, con este método ya verificado. Tampoco se cambia
`_search`.

## Pruebas

`tests/unit/orm/test_order_to_sql.py`, sobre `test_orm.category` y
`test_orm.message`, comparando `SQL.code`:

1. orden simple con dirección y nulos;
2. `reverse` invierte dirección y nulos;
3. orden vacío usa `_order`;
4. booleano con `COALESCE`;
5. `many2one` a un comodelo con `_order` no `id`: `LEFT JOIN` y delegación;
6. `x_id.id`: ordena por la columna sin unir;
7. guarda de ciclo (`parent` de `category`, cuyo `_order` es `name`):
   termina;
8. campo inexistente → `ValueError`; orden inválido → `UserError`;
9. `_order_groupby` recibe las columnas.

Control de anulación por rama: `reverse`, `COALESCE`, la rama `many2one`, la
guarda de ciclo.
