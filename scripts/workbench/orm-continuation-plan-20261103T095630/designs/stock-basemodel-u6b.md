# U6b — `stock.location` declara su identidad y adopta `BaseModel`

Fecha: 2026-11-23T22:53:46. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U6
(partida en U6a, la ruta, ya integrada en su rama, y U6b, la ubicación).

Referencia (`odoo-tools@abe4040ec1`, Odoo 19 Community):
odoo19c: addons/stock/models/stock_location.py:13-20 — `_name = 'stock.location'`,
`_description = "Inventory Locations"`, `_parent_name = "location_id"`,
`_parent_store = True`, `_order = 'complete_name, id'`,
`_rec_names_search = ['complete_name', 'barcode']`, `_check_company_auto = True`;
`_unlink_except_master_data` con `@api.ondelete(at_uninstall=False)`
(`:201-204`); `write(self, vals)` por recordset con sus cinco guardas y la
propagación del archivado a las hijas, que delega en `super().write(values)`
(`:220-264`); `unlink` que borra la rama `child_of` (`:266-267`); `create`
(`:283-287`); `copy_data` que devuelve la lista con «(copy)» (`:289-295`).
Sus filas ACL son tres
(odoo19c: addons/stock/security/ir.model.access.csv:4-6).

## Qué cambia

1. `StockLocation` declara los siete atributos de clase de la fuente y
   hereda `models.BaseModel` además de `DefaultGetMixin`. `_parent_name` es
   `location`, el nombre del campo en este árbol (precedente:
   `stock.package`, `_parent_name = 'parent_package'`). La tabla ya es
   `stock_location`, la que `_name` deriva.
2. `ir.model.access.csv` de `stock` gana las tres filas de la fuente.
3. `write(self, vals)` sustituye a `write(self, **vals)` con `setattr`:
   las cinco guardas recorren el recordset como la fuente, el archivado se
   propaga a las hijas por `child_of` salvo con `do_not_check_quant` en el
   contexto, y el resto delega en `super().write(vals)`.
4. `unlink` borra la rama entera (`child_of` sobre `self.ids`) por
   `super().unlink()`; la guarda de la ubicación entre empresas pasa de
   `check_can_delete` a `_unlink_except_master_data` con
   `@api.ondelete(at_uninstall=False)`, que `BaseModel.unlink` ejecuta.
5. `copy_data` devuelve la lista de `super().copy_data`, con «(copy)» si
   `default` no trae nombre.
6. El reverso de `stock.quant.location` toma el nombre de la fuente,
   `quant_ids` (odoo19c: addons/stock/models/stock_location.py:80); se
   llamaba `quants`, así que `is_empty`, `check_can_be_used` y la colocación
   de `product_strategy.py` leían un atributo inexistente. Migración
   `0034_port_location_quant_ids` (sólo estado de Django).
7. Los accesores entre dos `BaseModel` pasan a recordset: los 33 de la
   ubicación (padre, almacén, `child_ids`, `quants`, movimientos, albaranes,
   reglas…) y las 28 claves foráneas de otros `BaseModel` hacia ella
   (`location`, `location_dest`, `lot_stock`…). Los `is None` sobre ellas
   pasan a verdad y su API de gestor a iterar o a `ids`.

`parent_path`, `complete_name`, `warehouse` y `next_inventory_date` se
siguen recalculando en `save()` (divergencia 1 del docstring), que también
cubre `objects.create`; `_parent_store` no duplica la escritura porque el
recálculo de `save()` reescribe la misma ruta.

Prueba: `tests/unit/stock/test_stock_location_recordset.py`.

Anulación, restaurada con `cmp`: retirar la propagación del archivado en
`write` tumba sólo `test_archiving_a_branch_archives_its_children`.

## Citas de la fuente por archivo

- `addons/stock/models/stock_location.py`: odoo19c: addons/stock/models/stock_location.py:13-300.
- `addons/stock/models/product_strategy.py`: odoo19c: addons/stock/models/product_strategy.py:133-170.
- `addons/stock/models/stock_quant.py`: odoo19c: addons/stock/models/stock_quant.py:56-59,
  odoo19c: addons/stock/models/stock_quant.py:125-140,
  odoo19c: addons/stock/models/stock_quant.py:606-620,
  odoo19c: addons/stock/models/stock_quant.py:935-950
  y odoo19c: addons/stock/models/stock_quant.py:996-1010.
- `addons/stock/models/stock_lot.py`: odoo19c: addons/stock/models/stock_lot.py:168-185.
- `addons/stock/models/stock_move_line.py`: odoo19c: addons/stock/models/stock_move_line.py:73-75.
- `addons/stock/models/stock_orderpoint.py`: odoo19c: addons/stock/models/stock_orderpoint.py:258-262
  y odoo19c: addons/stock/models/stock_orderpoint.py:643-660.
- `addons/stock/models/stock_picking.py`: odoo19c: addons/stock/models/stock_picking.py:816-850
  y odoo19c: addons/stock/models/stock_picking.py:1102-1110.
- `addons/purchase_stock/models/purchase_order.py`: odoo19c: addons/purchase_stock/models/purchase_order.py:55-62.
- `addons/purchase_stock/models/stock.py`: odoo19c: addons/purchase_stock/models/stock.py:339-345.
- `addons/purchase_stock/models/stock_rule.py`: odoo19c: addons/purchase_stock/models/stock_rule.py:394-400.

Pruebas: `tests/unit/stock/test_stock_location_recordset.py`,
`tests/unit/stock/test_stock_location_warehouse.py` y
`tests/integration/stock/test_stock_orderpoint.py`.

## Símbolos tocados por archivo

- `addons/purchase_stock/models/purchase_order.py`: `_compute_effective_date`.
- `addons/purchase_stock/models/stock.py`: `_compute_effective_date`, `_compute_purchase_order_ids`.
- `addons/purchase_stock/models/stock_rule.py`: `_push_prepare_move_copy_values`.
- `addons/stock/models/product_strategy.py`: `get_putaway_location`.
- `addons/stock/models/stock_location.py`: `Meta`, `StockLocation`, `__str__`, `_get_putaway_strategy`, `_unlink_except_master_data`, `_weights_by_product`, `check_can_be_used`, `check_replenish_location`, `check_scrap_location`, `child_internal_location_ids`, `child_of`, `child_of_domain`, `compute_complete_name`, `compute_next_inventory_date`, `compute_parent_path`, `compute_warehouse`, `copy_data`, `create`, `default_get`, `get_next_inventory_date`, `get_weight`, `is_empty`, `is_outgoing`, `name_create`, `refresh_computed_fields`, `save`, `search_is_empty`, `unlink`, `write`.
- `addons/stock/models/stock_lot.py`: `_compute_single_location`, `_set_single_location`.
- `addons/stock/models/stock_move_line.py`: `location_dest_usage`, `location_usage`.
- `addons/stock/models/stock_orderpoint.py`: `_compute_warehouse_id`, `_get_replenishment_order_notification`.
- `addons/stock/models/stock_picking.py`: `_compute_state`, `_onchange_location_id`, `save`.
- `addons/stock/models/stock_quant.py`: `_apply_inventory`, `_compute_inventory_date`, `_onchange_inventory_quantity`, `_onchange_location_or_product_id`, `_onchange_product_id`, `check_location_id`, `check_quantity`, `compute_company`, `cyclic_inventory_frequency`, `storage_category`, `warehouse`, `write`.

La mayoría de los símbolos de `stock_location.py` sólo cambian de forma:
`black` sobre el cuerpo de la clase, que el ciclo de estilo mide entero
porque la cabecera de la clase cambió.

## Lo que este corte no cierra

Los cuatro calculados almacenados (`parent_path`, `complete_name`,
`warehouse`, `next_inventory_date`) se siguen recalculando en `save()` y no
por `compute=… store=True`: sucesor `stock-location-stored-computes-0397`.
`_get_putaway_strategy` y `get_putaway_location` comparan `package` y
`packaging` con `None` donde la fuente prueba verdad: sucesor
`stock-putaway-package-truthiness-0397`.
