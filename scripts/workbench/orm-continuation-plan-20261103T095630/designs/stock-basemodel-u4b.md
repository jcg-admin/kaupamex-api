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

4. `origin_returned_move` es ahora recordset: `_is_purchase_return`
   comprueba su verdad en vez de `is None`
   (`odoo19c: addons/purchase_stock/models/stock_move.py`).

## Defectos heredados de U3 y U4a que este corte destapa

Medidos al convertir el movimiento; los cuatro se corrigen aquí.

- `orm.utils.browse` devuelve un `AccessQuerySet`, sin `ids` ni `unlink`
  (`src/orm/models.py:1132-1150`, `_create_result`, lo declara). Lo usaban
  `StockQuant.create` y `StockWarehouse.create` como valor de retorno, y
  `StockMoveLine._action_done` y `_free_reservation` para llamar a
  `unlink()`. `create` pasa a devolver `cls._create_result(...)` y los dos
  borrados a `<registro>.browse(ids).unlink()`, el recordset de la fuente
  (`odoo19c: addons/stock/models/stock_move_line.py:845,851`).
- `_free_reservation` limpiaba los orígenes con
  `fields.Command.clear(movimiento.move_orig_ids)`. Con un argumento esa
  forma sólo construye la tupla; con el gestor de Django vaciaba la tabla, con
  el recordset ya no hace nada. Pasa a
  `write({'procure_method': 'make_to_stock', 'move_orig_ids':
  [Command.clear()]})`, como la fuente (`odoo19c: :846-850`).
- `StockMove._normalize_create_values` leía `values['picking'].state`, y
  `copy` entrega el albarán como id: `copy()` de un movimiento lanzaba
  `AttributeError`. La fuente hace
  `self.env['stock.picking'].browse(vals.get('picking_id'))`
  (`odoo19c: addons/stock/models/stock_move.py:823`): se resuelve el id.

Símbolos cuya forma cambia: `StockMove.write`, `StockMove.unlink`,
`StockMove._normalize_create_values`, `StockQuant.create`,
`StockWarehouse.create`, `StockMoveLine._action_done`,
`StockMoveLine._free_reservation`, `_is_purchase_return`,
`StockPicking._log_activity_get_documents`.

Prueba: `tests/unit/stock/test_stock_move_recordset_crud.py`. Anulación,
cada una restaurada con `cmp`: reponer la forma de un argumento de
`Command.clear` y retirar la resolución del id del albarán tumban sólo
`test_free_reservation_clears_the_origins_of_the_invaded_move`; devolver el
`QuerySet` en `StockQuant.create` tumba sólo
`test_quant_create_returns_a_recordset`.

## Símbolos tocados por archivo

Derivados del AST del diff; la adopción de recordset cambia el cuerpo de
cada uno sin cambiar su contrato salvo los nombrados arriba.

- `addons/purchase_stock/models/purchase_order.py`: `_add_reference`, `_remove_reference`.
- `addons/purchase_stock/models/purchase_order_line.py`: `_check_orderpoint_picking_type`, `_get_outgoing_incoming_moves`, `_get_po_line_moves`, `_update_move_date_deadline`, `delete_cancelling_moves`.
- `addons/purchase_stock/models/stock_move.py`: `_clean_merged`, `_get_purchase_line_and_partner_from_chain`, `_is_purchase_return`, `_prepare_move_split_vals`.
- `addons/stock/models/stock_lot.py`: `_check_product_change`.
- `addons/stock/models/stock_move.py`: `StockMove`, `_action_confirm`, `_apply_merge`, `_break_mto_link`, `_create_backorder`, `_do_unreserve`, `_generate_serial_move_line_commands`, `_get_available_move_lines_in`, `_get_available_move_lines_out`, `_get_picked_quantity`, `_get_upstream_documents_and_responsibles`, `_key_assign_picking`, `_merge_moves`, `_merge_moves_fields`, `_normalize_create_values`, `_onchange_lot_ids`, `_prepare_move_split_vals`, `_quantity_sml`, `_recompute_state`, `_search_picking_for_assignation_domain`, `_set_lot_ids`, `_set_quantity_done_prepare_vals`, `_set_references`, `_skip_push`, `_update_reserved_quantity_vals`, `has_lines_without_result_package`, `lot_ids`, `move_lines_count`, `unlink`, `write`.
- `addons/stock/models/stock_move_line.py`: `_action_done`, `_apply_putaway_strategy`, `_compute_location_id`, `_compute_picked`, `_compute_product_uom_id`, `_get_aggregated_product_quantities`, `_get_similar_move_lines`, `_put_in_pack`, `_synchronize_quant`, `action_open_reference`, `create`, `current_picking_first`, `description_picking`, `is_inventory`, `is_locked`, `move_partner`, `origin`, `reference`, `save`, `scheduled_date`, `scrap`, `unlink`, `write`.
- `addons/stock/models/stock_picking.py`: `_add_reference`, `_get_impacted_pickings`, `_get_next_transfers`, `_log_activity_get_documents`, `_onchange_location_id`, `_remove_reference`.
- `addons/stock/models/stock_quant.py`: `create`.
- `addons/stock/models/stock_reference.py`: `StockReference`, `picking_ids`.
- `addons/stock/models/stock_rule.py`: `_run_push`.
- `addons/stock/models/stock_warehouse.py`: `create`.

## Lo que este corte no cierra

U4c (`StockScrap`, `StockPicking`), U5 y U6 siguen en la partición.
