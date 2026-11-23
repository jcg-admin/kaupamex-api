# U4a — la línea de movimiento de `stock` adopta `BaseModel`

Fecha: 2026-11-23T17:09:41. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U4a.

Referencia: `stock.move.line` declara `write(self, vals)` y `unlink(self)`
sobre el recordset (`odoo19c: addons/stock/models/stock_move_line.py:421-546`,
`:557-575`).

Prueba del corte: `tests/unit/stock`, `tests/integration/stock`,
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

## Símbolos

| Archivo | Símbolos |
|---|---|
| `addons/stock/models/stock_move_line.py` | `StockMoveLine`, `write`, `unlink`, `_action_done`, `_check_entire_pack` |
| `addons/stock/models/stock_lot.py` | `_product_qty`, `_find_parent_lots`, `_find_delivery_ids_by_lot` |
| `addons/stock/models/stock_picking.py` | (comprobación de `product` en las líneas) |

## Lo que este corte no cierra

Los otros 17 métodos de clase que reciben una lista de líneas
(`_action_done`, `_put_in_pack`, `action_put_in_pack`…) no chocan con el
contrato de `BaseModel` y conservan su forma; llevarlos a métodos de
recordset es el sucesor `stock-move-line-recordset-methods-0397`. U4b, U4c, U5
y U6 siguen en la partición.
