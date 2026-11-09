# Diseño — unidad 5 de `read_group`: `_read_group`

Referencia: odoo-tools `abe4040ec`, `odoo/orm/models.py:1861-1952`.

Contrato: `_read_group(domain, groupby=(), aggregates=(), having=(), offset=0,
limit=None, order=None) -> list[tuple]`. ACL de lectura; `query =
self._search(domain)` (reglas incluidas); `Query` vacío → sin agrupado, una
fila de valores vacíos (PostgreSQL siempre devuelve una fila sin `GROUP BY`);
con agrupado, `[]`. Ventana en el `Query`; términos de agrupado
(`_read_group_groupby`) y de agregado (`_read_group_select`); con agrupado,
`ORDER BY` (`_read_group_orderby`), `GROUP BY` y `HAVING`
(`_read_group_having`); una consulta; posproceso por columna
(`_read_group_postprocess_groupby/aggregate`).

Todas las piezas existen (unidades 1-4 y `_search` → `Query`). Sin
consumidores vivos en Kaupamex (medido: la única mención es un docstring de
`base_vat`). Adaptación: `self._search` es `classmethod` y usa el entorno
activo; `_read_group` se llama sobre el recordset del entorno activo.

Pruebas (RED) en `tests/unit/orm/test_read_group.py`, ejecutando SQL sobre
filas sembradas: agrupado many2one con recordsets; agregados `__count` y
`sum`; `HAVING`; orden; vacío sin y con agrupado; regla de un usuario normal
(no ve los grupos de filas prohibidas).
