# U4c — el albarán y el desecho de `stock` adoptan `BaseModel`

Fecha: 2026-11-23T19:24:01. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U4c.
Depende de U4b (`move_ids` ya es recordset).

Referencia (`odoo-tools@abe4040ec1`, Odoo 19 Community):

- `stock.picking`: `create` (`addons/stock/models/stock_picking.py:1117-1137`),
  `write(self, vals)` (`:1139-1168`) con la guarda del tipo de operación
  sobre todos los albaranes y la propagación a
  `self.move_ids.filtered(...).write(after_vals)`, y `unlink(self)`
  (`:1170-1173`): `self.move_ids._action_cancel()`,
  `self.move_ids.unlink()`, `super().unlink()`.
- `_put_in_pack` borra las líneas del paquete con
  `self.move_line_ids.filtered(...).unlink()` (`:1910`).
- `stock.scrap`: `_unlink_except_done` con `@api.ondelete(at_uninstall=False)`
  sobre `self.mapped('state')` (`addons/stock/models/stock_scrap.py:120-123`).

## Qué cambia

`StockPicking` y `StockScrap` heredan `models.BaseModel`.

1. `StockPicking.write` asignaba con `setattr`, guardaba y devolvía
   `self`: pasa a recorrer `self` en las guardas, renumerar por albarán,
   delegar en `super().write(vals)` y propagar a los movimientos con su
   `write` (que ya es de recordset), como la fuente. Devuelve el resultado de
   `super().write`.
2. `StockPicking.unlink` recorría `move_ids.all()` y borraba con
   `move.delete()`: pasa a cancelar los movimientos, borrarlos con su
   `unlink` de recordset (que aplica la guarda de cadena a todos antes de
   borrar) y delegar en `super().unlink()`.
3. `StockScrap.delete` era la guarda del borrado: se retira y
   `_unlink_except_done` lleva `@api.ondelete(at_uninstall=False)` sobre el
   recordset, como la fuente; `BaseModel.unlink` la invoca.
4. El borrado de líneas por paquete usaba `QuerySet.delete()`, que no pasa
   por `StockMoveLine.unlink` ni libera la reserva: pasa a
   `filtered(...).unlink()` (`:1910`).
5. Los reversos entre dos `BaseModel` pasan a recordset: `move_ids`,
   `move_line_ids`, `backorder_ids`, `return_ids`, `scraps`,
   `package_history_ids` del albarán; `move_ids` del desecho; `pickings` del
   tipo de operación, de la venta y del proyecto; `scraps` del producto, el
   lote, el paquete, la unidad y la etiqueta. `picking` y `scrap` del
   movimiento y de la línea unen ahora dos `BaseModel`: sus comprobaciones
   `is None` pasan a ser de verdad.
6. Se retira el `from orm.utils import browse` que U4b dejó sin uso en
   `stock_move_line.py`.

Prueba: `tests/unit/stock/test_stock_picking_recordset_crud.py` — escritura
y borrado sobre un recordset de dos albaranes, y el desecho hecho rechazado
por `unlink`.

## Lo que este corte no cierra

`_autoconfirm_picking` en `create` sigue divergente (D-8 del docstring de la
clase). U5 y U6 siguen en la partición.
