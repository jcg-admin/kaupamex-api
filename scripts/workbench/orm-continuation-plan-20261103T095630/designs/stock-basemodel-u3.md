# U3 — el ciclo almacén, tipo de operación, regla y punto de pedido adopta `BaseModel`

Fecha: 2026-11-23T15:56:01. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U3.

Referencia:
- `stock.warehouse`: `write(self, vals)`, `unlink(self)` y los auxiliares
  `_create_missing_locations`, `_update_location_reception`,
  `_update_location_delivery`, `_update_reception_delivery_resupply` y
  `_update_name_and_code` son métodos de recordset
  (`odoo19c: addons/stock/models/stock_warehouse.py:185-308`, `:689-705`,
  `:867-873`, `:923-955`);
- `purchase_stock` extiende `_update_name_and_code` sobre el mismo recordset
  (`odoo19c: addons/purchase_stock/models/stock.py:116-122`).

Prueba del corte: `tests/unit/stock`, `tests/integration/stock` y el subconjunto
derivado de los cuatro modelos (`tests/integration/sale/test_stock*.py`,
`tests/unit/purchase_stock/test_replenishment_multiple_alternative.py`, …).

## Qué cambia

`StockWarehouse`, `StockPickingType`, `StockRule` y
`StockWarehouseOrderpoint` heredan `models.BaseModel` en una sola unidad,
porque forman un ciclo de claves (`warehouse` ↔ `picking_type` ↔ `rule`).

1. Los métodos del almacén que recibían una lista (`write(cls, warehouses,
   vals)` y sus cinco auxiliares) pasan a la forma de la fuente: `self` es el
   recordset, `cls.write([w], x)` pasa a `w.write(x)`, `write` devuelve
   `True` y `unlink` delega en `super().unlink()`. `create` devuelve el
   recordset de los almacenes creados.
2. El eslabón de `purchase_stock` sobre `_update_name_and_code` deja de ser
   método de clase: `chain_method` conserva el descriptor, así que los dos
   eslabones tienen que ser de la misma clase (H-API-738).
3. Los Many2one entre dos `BaseModel` pasan a recordset: `is None` pasa a
   comprobación de verdad, en las cuatro clases y en sus llamadores
   (`purchase_stock`, `stock_picking`, `stock_rule`, `stock_orderpoint`).
   `resupply_wh_ids`, M2M del almacén consigo mismo, se lee con `ids`.

## Símbolos

| Archivo | Símbolos |
|---|---|
| `addons/stock/models/stock_warehouse.py` | `StockWarehouse`, `create`, `write`, `unlink`, `_create_missing_locations`, `_get_all_routes`, `_update_location_delivery`, `_update_location_reception`, `_update_name_and_code`, `_update_reception_delivery_resupply` |
| `addons/stock/models/stock_picking.py` | `StockPickingType`, `__str__`, `compute_default_location_dest`, `compute_default_location_src`, `compute_warehouse`, `warehouse_address`, `write` |
| `addons/stock/models/stock_rule.py` | `StockRule`, `_push_prepare_move_copy_values` |
| `addons/stock/models/stock_orderpoint.py` | `StockWarehouseOrderpoint`, `_compute_warehouse_id`, `_get_default_route`, `_get_multiple_rounded_qty`, `_lead_days_values`, `_procure_orderpoint_confirm`, `_qty_pair`, `action_product_forecast_report`, `allowed_replenishment_uom_ids`, `product_category`, `product_tmpl_id`, `product_uom`, `rule_ids`, `save`, `unwanted_replenish` |
| `addons/purchase_stock/models/stock.py` | `_update_name_and_code`, `_compute_buy_to_resupply`, `_get_all_routes`, `_install_warehouse`, `_inverse_buy_to_resupply`, `_inverse_supplier_id` |

## Lo que este corte no cierra

`StockPickingType.write` conserva el cuerpo de un registro (lee `self.company`
y `self.sequence_id` sin recorrer `self`); llevarlo al bucle de la fuente es
parte de esta unidad si el subconjunto lo exige, y si no queda en el sucesor
`stock-picking-type-write-multi-0397`. U4–U6 siguen en la partición.
