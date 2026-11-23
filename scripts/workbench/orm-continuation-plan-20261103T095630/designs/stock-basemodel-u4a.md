# U4a — la línea de movimiento de `stock` adopta `BaseModel`

Fecha: 2026-11-23T17:09:41. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U4a.

Referencia: `stock.move.line` declara `write(self, vals)` y `unlink(self)`
sobre el recordset (`odoo19c: addons/stock/models/stock_move_line.py:421-546`,
`:557-575`).

Prueba del corte: `tests/unit/stock/test_stock_move_line_recordset_crud.py`, `tests/unit/stock`, `tests/integration/stock`,
`tests/unit/purchase_stock` y el subconjunto derivado de `StockMoveLine`,
`StockLot` y `StockPackage`.

## Qué cambia

`StockMoveLine` hereda `models.BaseModel`. Su `write(cls, lines, vals)` y su
`unlink(cls, lines)` chocaban con la API de `BaseModel`: pasan a
`write(self, vals)` y `unlink(self)`, con `lines = list(self)` al entrar,
y `write` devuelve `True`. Las dos llamadas internas que pasaban una lista a
`unlink` construyen el recordset con `orm.utils.browse`.

Las relaciones entre dos `BaseModel` pasan a recordset: `lot`, `package`,
`package_history`, `product`, `product_uom` y `result_package` de la
línea, y los reversos `move_line_ids` de lote, paquete e historial,
`stock_move_lines` de producto y unidad, y `produce_line_ids`/
`consume_line_ids`. Las comprobaciones `is None` sobre esas relaciones pasan
a ser de verdad (las de `attname` se quedan); las consultas de `stock_lot`
que filtraban `self.move_line_ids` salen del gestor de `StockMoveLine`.

## La firma de `_update_reserved_quantity`

La prueba nueva de `write` destapó un `TypeError` latente: los tres
llamadores de `stock.move.line` pasan `lot_id`, `package_id` y `owner_id`,
que son los nombres de la fuente
(`odoo19c: addons/stock/models/stock_quant.py:1108`), y el porte de
`StockQuant._update_reserved_quantity` los había renombrado a `lot`,
`package` y `owner`. El `write` de clase nunca se ejecutaba, y `unlink` de
una línea reservada habría fallado igual. La firma del quant vuelve a la de
la fuente y sus dos llamadores internos (`_clean_reservations`) se ajustan.

Control de anulación: con la cabecera vieja de `write` (método de clase que
recibe una lista) cae `test_write_takes_the_values_on_the_recordset` y
ninguna otra.

## Cambios sólo de forma

Cambiar la base hace del corte la deuda de estilo de `StockMoveLine`: 51
E741 (la variable `l`, renombrada por AST función a función a un nombre libre
en cada una), E501 y E221 resueltos con `black` sobre las líneas señaladas.
Los f-strings de los cuatro archivos son iguales por AST. Cambian de AST sin
cambiar de conducta: `_apply_putaway_strategy`, `_check_destinations`,
`_check_lot_product`, `_create_and_assign_production_lot`,
`_get_aggregated_product_quantities`, `_get_aggregated_properties`,
`_get_lines_and_packages_to_pack`, `_get_lines_not_entire_pack`,
`_onchange_putaway_location`, `_pre_put_in_pack_hook`,
`_prepare_package_history_vals`, `_put_in_pack`, `_should_set_package`,
`action_revert_inventory` y `get_move_line_quant_match`.

## Símbolos

| Archivo | Símbolos |
|---|---|
| `addons/stock/models/stock_move_line.py` | `StockMoveLine`, `write`, `unlink`, `_action_done`, `_check_entire_pack` |
| `addons/stock/models/stock_lot.py` | `_product_qty`, `_find_delivery_ids_by_lot`, `_find_delivery_ids_by_lot_iterative` |
| `addons/stock/models/stock_quant.py` | `_update_reserved_quantity`, `_clean_reservations` |
| `addons/stock/models/stock_picking.py` | (comprobación de `product` en las líneas) |

## Lo que este corte no cierra

Los otros 17 métodos de clase que reciben una lista de líneas
(`_action_done`, `_put_in_pack`, `action_put_in_pack`…) no chocan con el
contrato de `BaseModel` y conservan su forma; llevarlos a métodos de
recordset es el sucesor `stock-move-line-recordset-methods-0397`. U4b, U4c, U5
y U6 siguen en la partición.
