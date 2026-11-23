# U2 — paquetes, historial, lotes y quants de `stock` adoptan `BaseModel`

Fecha: 2026-11-23T13:51:20. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U2,
más la reconciliación de `create`/`write` que esa sección pide fijar antes
de U2.

Referencia:
- `write(self, vals)` con las tres guardas y `super().write(vals)`
  (`odoo19c: addons/stock/models/stock_package.py:289-314`);
- `write(self, vals)` del quant en modo inventario
  (`odoo19c: addons/stock/models/stock_quant.py:351-361`);
- `unpack` desliga los hijos y mueve los quants
  (`odoo19c: addons/stock/models/stock_package.py:316-325`);
- `stock.putaway.rule`: `_compute_storage_category` almacenado con
  `@api.depends('sublocation')`, `create` que delega y `write` que rechaza
  el cambio de empresa (`odoo19c: addons/stock/models/product_strategy.py:63-112`).

Prueba del corte: `tests/integration/stock/test_putaway_rule_storage_category.py`,
más `tests/unit/stock`, `tests/integration/stock` y el subconjunto derivado
de los símbolos tocados.

## La regla de reconciliación

Un modelo que adopta `BaseModel` toma la firma de la fuente: `write(self,
vals)` recorre `self` registro a registro y termina en
`super().write(vals)`; `create` delega en `super().create`; un campo
calculado almacenado se declara con `compute=`, `store=True` y su
`@api.depends`, en vez de recalcularse a mano en `create` y `write`.

## Qué cambia

`StockPackage`, `StockPackageHistory`, `StockLot` y `StockQuant` heredan
`models.BaseModel` (`StockLot` además de `MailThread` y
`MailActivityMixin`, como `PurchaseOrder`). Las relaciones entre dos
`BaseModel` pasan a recordset:

- de avance: `lot`, `package`, `package_dest`, `parent_package`,
  `outermost_dest`, `parent_dest`, `parent_orig`, `product` (en lote y
  quant) y `package_type` (en paquete);
- reversos: `quants` y `quant_ids`, `child_package_ids`,
  `child_package_dest_ids`, los cuatro `history_*`, `lots` y `quants` de
  `ProductProduct`, y `package_ids` de `StockPackageType`.

Por eso las comprobaciones `is None` sobre esas relaciones pasan a ser
comprobaciones de verdad, y la API de gestor (`.filter`, `.all`, `.count`,
`.values_list`) sobre esos reversos pasa a `filtered`, `len` e `ids`. Los
dos `update` masivos de `unpack` y `_check_move_lines_map_quant_package`
siguen siendo consultas sobre el gestor de la clase, sin pasar por `write`,
como antes.

## Símbolos

| Archivo | Símbolos |
|---|---|
| `addons/stock/models/stock_package.py` | `StockPackage`, `write`, `unpack`, `dest_complete_name`, `_apply_package_dest_for_entire_packs`, `action_remove_package`, `compute_complete_name`, `compute_package_info`, `compute_parent_path`, `outermost_package`, `owner` |
| `addons/stock/models/stock_package_history.py` | `StockPackageHistory`, `_get_complete_dest_name_except_outermost`, `package_type` |
| `addons/stock/models/stock_lot.py` | `StockLot`, `_compute_single_location`, `_product_qty`, `_set_single_location` |
| `addons/stock/models/stock_quant.py` | `StockQuant`, `write`, `_load_records_write`, `_compute_display_name`, `_get_available_quantity`, `_get_gs1_barcode`, `_onchange_location_or_product_id`, `_onchange_serial_number`, `_update_available_quantity`, `action_inventory_history`, `action_view_stock_moves`, `check_lot_id`, `check_product_id`, `check_quantity`, `is_outdated`, `last_count_date`, `product_tmpl_id`, `product_uom`, `sn_duplicated` |
| `addons/stock/models/stock_package_type.py` | `has_quants` |
| `addons/stock/models/stock_picking.py` | `_check_entire_pack` |
| `addons/stock/models/stock_location.py` | `check_can_be_used` |
| `addons/stock/models/product_strategy.py` | `StockPutawayRule`, `storage_category`, `_compute_storage_category`, `create`, `write` |

## Lo que este corte no cierra

Los cálculos almacenados de `StockPackage` siguen recalculándose a mano en
`refresh_computed_fields`; llevarlos a `compute=` es trabajo de la misma
regla, pendiente y registrado en el sucesor `stock-package-stored-computes-0397`.
U3–U6 siguen en la partición.
