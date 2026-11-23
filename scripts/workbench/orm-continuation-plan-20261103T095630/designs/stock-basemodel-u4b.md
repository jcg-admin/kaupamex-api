# U4b — el movimiento y la referencia de `stock` adoptan `BaseModel`

Fecha: 2026-11-23T18:23:49. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/stock-basemodel-adoption-research.md`, sección 6, fila U4b.

Referencia: `stock.move` declara `write(self, vals)` con sus guardas sobre
el recordset y `unlink` que borra primero las líneas
(`odoo19c: addons/stock/models/stock_move.py:833-905`, `:2337-2343`); los
M2M `move_orig_ids`, `move_dest_ids`, `reference_ids` y
`created_purchase_line_ids` se escriben con comandos
(`odoo19c: addons/purchase_stock/models/stock_move.py:100-114`).

Prueba del corte: `tests/unit/stock`, `tests/integration/stock`, los
directorios de `purchase` y el subconjunto derivado de los dos modelos.

## Qué cambia

`StockMove` y `StockReference` heredan `models.BaseModel`.

1. `StockMove.write` asignaba con `setattr` y guardaba, así que no aceptaba
   comandos M2M: las guardas recorren `self` y el resto delega en
   `super().write(vals)`; los ganchos de reabastecimiento y referencias
   corren por movimiento. `unlink` recorre `self`, borra las líneas con su
   `unlink` (que libera la reserva) y delega en `super().unlink()`.
2. Los reversos entre dos `BaseModel` pasan a recordset: `move_line_ids`,
   `move_dest_ids`, `move_orig_ids`, `returned_move_ids` y `reference_ids`
   del movimiento, `move_ids` de la referencia y de la línea de compra,
   `move_dest_ids` de la línea de compra, `created_purchase_line_ids` y
   `reference_ids` de la orden de compra. Su API de gestor pasa a recorrer
   el recordset y a `write` con `Command.link`/`unlink`/`set`/`clear`.
   Los reversos que cuelgan de `stock.picking` y `stock.scrap` no cambian:
   esos dueños aún no son `BaseModel` (U4c).
3. `move` de la línea de movimiento une ahora dos `BaseModel`: sus
   comprobaciones `is None` pasan a ser de verdad.

## Lo que este corte no cierra

U4c (`StockScrap`, `StockPicking`), U5 y U6 siguen en la partición.
