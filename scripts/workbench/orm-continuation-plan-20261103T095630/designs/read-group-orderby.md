# Diseño — unidad 3 de `read_group`: `_read_group_orderby`

Referencia: odoo-tools `abe4040ec`, `odoo/orm/models.py`
(`_read_group_orderby`) y `regex_order_part_read_group` (`:105-111`).

Contrato: `(order, groupby_terms, query) -> SQL`. Sin `order` se ordena por los
términos de agrupado y no se recorren los many2one; sin nada, `SQL()`. Cada
parte casa con `regex_order_part_read_group` (si no, `ValueError`); un término
que no es de agrupado se ordena como agregado (`_read_group_select`, y si no lo
es, `ValueError`); un many2one de agrupado cuyo comodelo no se ordena por `id`
se ordena con `_order_to_sql` y amplía su término de agrupado con
`query._order_groupby`; `day_of_week` se desplaza por `week_start` del idioma
(`mod(7 - %s + %s::int, 7)`); el resto, el término de agrupado con su
dirección y sus nulos.

Existe en Kaupamex: `_order_to_sql` (con `query._order_groupby`),
`_read_group_select`, `get_lang`. Falta: `regex_order_part_read_group`, que se
porta verbatim junto a `regex_read_group_spec`.

Pruebas (RED) en `tests/unit/orm/test_read_group_orderby.py`: vacío; orden por
defecto de los agrupados; dirección y nulos; agregado no agrupado; orden
inválido; término que no es ni uno ni otro; `day_of_week`; many2one con
`_order` de nombre (`test_orm.category.parent`, `_order = 'name'`).
