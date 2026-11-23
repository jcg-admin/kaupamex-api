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
6. Los dos onchange existían con nombres propios (`apply_company_filter`,
   `apply_warehouse_selectable`): pasan a `_onchange_company` y
   `_onchange_warehouse_selectable` con `@api.onchange`, como la fuente
   (odoo19c: addons/stock/models/stock_location.py:562-570); el segundo vacía
   `warehouse_ids` con `Command.clear()`. `warehouse_domain_ids` sigue como
   `property` sin columna, la divergencia ya declarada en el docstring del
   módulo.
7. Los reversos entre dos `BaseModel` pasan a recordset: `route_ids` de
   producto, categoría, tipo de paquete y almacén, `rule_ids`,
   `warehouse_ids`, `categ_ids`, `product_ids` de la ruta. Su API de gestor
   pasa a iterar, a `ids` y a `write` con `Command.link`/`unlink`; los
   `is None` sobre `route`, `ruta` y similares pasan a verdad.
   `_related_pks` de `stock_orderpoint.py` acepta el recordset.
8. `tests/unit/base/test_reflect_model_params_ordering.py` usaba
   `StockRoute` como modelo sin `_order`; ahora lo declara, y el sujeto pasa
   a `ReturnItem`, propio del L0 y sin `_name`.

Prueba: `tests/unit/stock/test_stock_route_recordset.py`. Anulación,
restaurada con `cmp`: retirar el archivado de reglas en `write` tumba sólo
`test_archiving_the_route_archives_rules_with_a_live_destination`.

## Citas de la fuente por archivo

- `addons/stock/models/stock_location.py`: odoo19c: addons/stock/models/stock_location.py:517-591.
- `addons/stock/models/stock_rule.py`: odoo19c: addons/stock/models/stock_rule.py:537-575.
- `addons/stock/models/stock_warehouse.py`: odoo19c: addons/stock/models/stock_warehouse.py:473-520
  y odoo19c: addons/stock/models/stock_warehouse.py:1145-1160.
- `addons/stock/models/stock_orderpoint.py`: odoo19c: addons/stock/models/stock_orderpoint.py:440-450.
- `addons/stock/models/stock_replenish_mixin.py`: odoo19c: addons/stock/models/stock_replenish_mixin.py:26-30.
- `addons/stock/models/product.py`: odoo19c: addons/stock/models/product.py:1309-1328.
- `addons/purchase_stock/models/product.py`: odoo19c: addons/purchase_stock/models/product.py:17-25.
- `addons/purchase_stock/models/stock.py`: odoo19c: addons/purchase_stock/models/stock.py:54-60.
- `addons/purchase_stock/models/stock_replenish_mixin.py`: odoo19c: addons/purchase_stock/models/stock_replenish_mixin.py:17-22.
- `addons/purchase_stock/models/stock_rule.py`: odoo19c: addons/purchase_stock/models/stock_rule.py:167-175.

Pruebas: `tests/unit/stock/test_stock_route_recordset.py`,
`tests/integration/sale/test_stock_product_surface.py` y
`tests/integration/stock/test_stock_orderpoint.py`.

## Símbolos tocados por archivo

- `addons/purchase_stock/models/product.py`: `_onchange_buy_route`.
- `addons/purchase_stock/models/stock.py`: `_compute_buy_to_resupply`, `_create_or_update_route`, `_get_replenishment_multiple_alternative`, `_inverse_buy_to_resupply`, `_inverse_route_id`, `_inverse_supplier_id`.
- `addons/purchase_stock/models/stock_replenish_mixin.py`: `_compute_show_vendor`, `_get_show_vendor`.
- `addons/purchase_stock/models/stock_rule.py`: `_filter_warehouse_routes`, `_is_valid_resupply_route_for_product`, `run`.
- `addons/stock/models/product.py`: `filter_has_routes`, `get_total_routes`, `parent_route_ids`, `total_route_ids`, `uom_route_ids`.
- `addons/stock/models/stock_location.py`: `StockRoute`, `_check_company_consistency`, `_onchange_company`, `_onchange_warehouse_selectable`, `copy_data`, `write`.
- `addons/stock/models/stock_orderpoint.py`: `_get_default_route`, `_get_default_rule`, `_prepare_procurement_values`, `_related_pks`, `effective_route`, `route_id_placeholder`, `rule_ids`.
- `addons/stock/models/stock_replenish_mixin.py`: `_get_allowed_route_domain`.
- `addons/stock/models/stock_rule.py`: `_check_company_consistency`, `_search_rule`, `_search_rule_for_warehouses`, `extract_rule`, `get_rule_for_routes`.
- `addons/stock/models/stock_warehouse.py`: `_apply_active_to_topology`, `_create_or_update_route`, `_find_or_create_global_route`, `_get_all_routes`, `_update_name_and_code`.

## Lo que este corte no cierra

`warehouse_domain_ids` como campo calculado sin columna (`:556-560`), hoy
`property`: sucesor `stock-route-warehouse-domain-0397`. `parent_route_ids` y
`total_route_ids` de la categoría devuelven un `QuerySet` donde la fuente
devuelve un recordset: sucesor `product-category-route-recordsets-0397`. U6b
(`stock.location`) sigue.
