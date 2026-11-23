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
`tests/integration/sale/test_product_expiry.py`, `tests/unit/stock/test_stock_picking_packages.py`,
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
| `addons/stock/models/stock_quant.py` | `StockQuant`, `write`, `_load_records_write`, `_gather`, `_compute_display_name`, `_get_available_quantity`, `_get_gs1_barcode`, `_onchange_location_or_product_id`, `_onchange_serial_number`, `_update_available_quantity`, `action_inventory_history`, `action_view_stock_moves`, `check_lot_id`, `check_product_id`, `check_quantity`, `is_outdated`, `last_count_date`, `product_tmpl_id`, `product_uom`, `sn_duplicated` |
| `addons/stock/models/stock_package_type.py` | `has_quants` |
| `addons/stock/models/stock_picking.py` | `_check_entire_pack` |
| `addons/stock/models/stock_location.py` | `check_can_be_used` |
| `addons/stock/models/stock_move_line.py` | `_compute_quantity` |
| `addons/product_expiry/models/stock_move_line.py` | `_compute_expiration_date` |
| `addons/stock/models/product_strategy.py` | `StockPutawayRule`, `storage_category`, `_compute_storage_category`, `create`, `write` |

## Lo que destapó el subconjunto

La primera ejecución del subconjunto derivado dio 22 fallos, con cinco causas:

- `_gather` anotaba `without_lot`, y un registro `BaseModel` no admite un
  atributo público que su modelo no declare (`__setattr__`, ≙ los
  `__slots__` de la fuente): la anotación pasa a `_without_lot`.
- `StockLot._product_qty` filtraba y agregaba sobre `self.quants`, que ahora
  es un recordset: la consulta sale del gestor de `StockQuant`.
- `quant_id` de la línea de movimiento es un Many2one no almacenado hacia un
  `BaseModel`, y vacío vale un recordset vacío: `_compute_quantity`
  (`addons/stock/models/stock_move_line.py`) y `_compute_expiration_date`
  (`addons/product_expiry/models/stock_move_line.py`) lo leen por verdad.
- La etiqueta de caducidad de `product_expiry` depende del contexto
  `formatted_display_name`. Un registro `BaseModel` lleva el contexto de su
  entorno, como en la fuente (`lot.with_context(...)`), no el del ámbito en
  que se lee; las pruebas pasan a `with_context`.
- La prueba de la categoría con `sublocation='no'` en `create` contradecía la
  fuente: un valor dado en `create` protege al campo calculado. Se retiró; la
  de `write` cubre el cálculo.

Control de anulación: sin `@api.depends('sublocation')` cae
`test_writing_the_sublocation_clears_the_category`, y sin la guarda de
empresa cae `test_changing_the_company_is_refused`; ninguna otra.

## Cambios sólo de forma

Al cambiar las bases, la huella de estilo de cada clase pasa a ser del corte,
así que se resolvió su deuda E501/E221/E741. Siete funciones cambian de AST
sin cambiar de conducta: `StockPackage._search_move_line_ids`, `has_issues`,
`json_popover` y `picking_ids` (variable `l` renombrada a `line`), y
`StockQuant._merge_quants`, `_run_least_packages_removal_strategy_astar` y
`_unlink_zero_quants` (SQL y docstrings partidos en el espacio, literales
concatenados de forma adyacente). Las cubre el mismo subconjunto de
`tests/unit/stock` y `tests/integration/stock`.

## Lo que este corte no cierra

Los cálculos almacenados de `StockPackage` siguen recalculándose a mano en
`refresh_computed_fields`; llevarlos a `compute=` es trabajo de la misma
regla, pendiente y registrado en el sucesor `stock-package-stored-computes-0397`.
Un registro leído desde un entorno con otro contexto vuelve a leer su
Many2one, cuando en la fuente la caché de registros se comparte entre
contextos; lo destapó `test_new_expiry_lot_assigns_computed_label_without_sql`
y queda en el sucesor `orm-cross-context-record-cache-0397`. U3–U6 siguen en
la partición.
