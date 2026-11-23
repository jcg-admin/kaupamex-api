# U6a — `stock.route` declara su identidad y adopta `BaseModel`

Fecha: 2026-11-23T22:15:35. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U6
(partida en U6a, la ruta, y U6b, la ubicación).

Referencia (`odoo-tools@abe4040ec1`, Odoo 19 Community):
odoo19c: addons/stock/models/stock_location.py:517-593 — `_name = 'stock.route'`,
`_description = "Inventory Routes"`, `_order = 'sequence'`,
`_check_company_auto = True`; `copy_data` que devuelve la lista de valores
con «(copy)» (`:546-552`); `write(self, vals)` que archiva o desarchiva las
reglas cuyo destino está activo y delega en `super()` (`:570-577`);
`_check_company_consistency` con `@api.constrains('company_id')`
(`:579-591`). Sus filas ACL son dos
(odoo19c: addons/stock/security/ir.model.access.csv:28-29).

## Qué cambia

1. `StockRoute` declara `_name`, `_description`, `_order` y
   `_check_company_auto` de la fuente, y hereda `models.BaseModel`. La
   tabla ya es `stock_route`, la que `_name` deriva.
2. `ir.model.access.csv` de `stock` gana las dos filas de la fuente
   (`access_stock_location_route_stock_manager`, `access_stock_location_route`).
3. `write(self, vals)` sustituye a `write(self, **vals)` con `setattr`:
   con `active` en los valores, las reglas de la ruta cuyo destino está
   activo se archivan o desarchivan con `action_archive`/`action_unarchive`,
   y el resto delega en `super().write(vals)`.
4. `copy_data` devuelve la lista de valores de `super().copy_data`, con el
   nombre «(copy)» cuando `default` no lo trae, como la fuente.
5. `check_company_consistency` pasa a `_check_company_consistency`
   (privado, como en la fuente) con `@api.constrains('company_id')`, que
   `BaseModel` ejecuta; el `clean()` que lo invocaba se retira.
6. `_onchange_warehouse_selectable` vacía `warehouse_ids` con
   `Command.clear()`; los reversos hacia modelos `BaseModel` pasan a
   recordset.

Prueba: `tests/unit/stock/test_stock_route_recordset.py`.

## Lo que este corte no cierra

`warehouse_domain_ids` y `_compute_warehouses` (`:556-560`) y
`_onchange_company` (`:562-565`) no están portados: sucesor
`stock-route-warehouse-domain-0397`. U6b (`stock.location`) sigue.
