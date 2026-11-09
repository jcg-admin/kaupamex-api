# Plan de la familia `_read_group` (odoo19c)

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo/orm/models.py`. Tamaño medido por AST (líneas): `_read_grouping_sets`
259, `_read_group` 91, `_read_group_select` 61, `_read_group_groupby` 105,
`_read_group_having` 28, `_read_group_orderby` 78, `_read_group_empty_value`
17, `_read_group_postprocess_groupby` 28, `_read_group_postprocess_aggregate`
32, `_read_group_expand_full` 3, `_read_group_fill_results` 70,
`_read_group_fill_temporal` 166, `_read_group_format_result` 81,
`_read_group_format_result_properties` 107, `read_group` 139,
`_read_group_groupby_properties` 106. Todos `absent` en el inventario.

## Lo que ya existe en Kaupamex

- `Query` con `select/groupby/having/order/limit/offset` y `_order_groupby`
  (`tools/query.py`); `_field_to_sql`, `_traverse_related_sql` y los `related`
  no almacenados (`267ade99`); `_order_to_sql`/`_order_field_to_sql`
  (`db29e327`); `Domain._to_sql` (`orm/domains.py`); `ir.rule._compute_domain`
  (`addons/base/models/ir_rule.py:436`); `READ_GROUP_*_GRANULARITY`
  (`orm/utils.py`).
- `web` tiene su propio `formatted_read_group` sobre Django
  (`addons/web/models/models.py:1515`), consumidor que tendría que delegar en
  `_read_group` cuando exista, como ya se hizo con `export_data`.

## Dependencia estructural

`_read_group` empieza con `query = self._search(domain)` y trabaja sobre ese
`Query` (`:1861-1952`). Aquí `_search` devuelve un `QuerySet` de Django
(divergencia declarada en `src/orm/models.py`, `_search`), con consumidores en
todo el árbol. Hace falta un camino que produzca el `Query` de la fuente
(`:5324-5395`: `Domain` → `_to_sql`, más el dominio de `ir.rule` cuando no es
`sudo`, más `active_test`).

Opciones:

1. `_search` pasa a devolver `Query`, como la fuente, y sus consumidores se
   adaptan. Es el contrato exacto; es la unidad más ancha del árbol.
2. Un método de adaptación que devuelva el `Query` de la fuente, consumido por
   `_read_group`, sin tocar `_search`. Contrato de `_read_group` exacto; un
   símbolo sin contraparte, declarado.

La elección cambia una superficie usada en todo el árbol: se registra aquí y
se plantea al ejecutor antes de implementarla. Mientras, avanzan las piezas
que no dependen de ella.

## Unidades, en orden

1. `_read_group_select` + `_read_group_having` (agregados y `HAVING` sobre un
   `Query`): no dependen del origen del `Query`.
2. `_read_group_groupby` (con granularidad temporal y numérica).
3. `_read_group_orderby`.
4. `_read_group_empty_value`, `_read_group_postprocess_groupby`,
   `_read_group_postprocess_aggregate`.
5. `_read_group` (necesita el `Query` del dominio: dependencia de arriba).
6. `_read_group_fill_*`, `_read_group_format_result*`, `read_group`,
   `_read_grouping_sets`, propiedades; y delegar `web.formatted_read_group`.
