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

7. **`scheduled_date` se porta**, porque es condición de la adopción: un
   `BaseModel` valida su `_order` y el de la fuente,
   `"priority desc, scheduled_date asc, id desc"`, nombraba un campo que no
   existía (estaba en el grupo bloqueado del docstring de la clase). Se porta
   almacenado, con `_compute_scheduled_date` (`:864-873`),
   `_set_scheduled_date` (`:925-931`) y el `pop` de `create` que lo escribe
   después de crear (`:1126-1134`). `Meta.ordering` pasa a
   `['-priority', 'scheduled_date', '-id']`. La migración
   `stock/0033_port_picking_scheduled_date` rellena las filas existentes con
   la misma regla, y con su `create_date` si no tienen movimientos pendientes.
8. **`_put_in_pack` escribía el paquete con `QuerySet.update`**, que no
   invalida la caché del ORM: tras la adopción, la línea seguía leyendo
   `result_package_id = None` aunque la fila tuviera el paquete. Pasa a
   `write` sobre el recordset, como la fuente
   (`addons/stock/models/stock_move_line.py:1111`).
9. `picking_type` y `picking` son ahora recordsets en el albarán y en la
   línea: las comprobaciones `is None` sobre ellos pasan a verdad
   (`picking_type_code` devolvía `False` en vez de `None`). En
   `StockMoveLine._compute_location_id` el albarán previo de una línea sin
   albarán es ahora `stock.picking()`, y leer un campo de un recordset vacío
   lanza `DoesNotExist` en este ORM: se toma `origen.picking or None`.
10. `write` renumera con `picking.write({'name': ...})`: la asignación al
    atributo de un registro no persiste.

La prueba heredada `test_write_propagates_date_done_to_finished_moves`
afirmaba que sólo los movimientos hechos de un albarán hecho reciben
`date_done`; la fuente escribe en todos los movimientos de los albaranes hechos
(`:1150-1151`). La prueba se ajusta a la fuente: un albarán hecho y otro
abierto, y sólo el primero propaga.

Prueba: `tests/unit/stock/test_stock_picking_recordset_crud.py`. Anulación,
restaurada con `cmp`: quitar `@api.ondelete` del desecho tumba sólo
`test_a_done_scrap_cannot_be_unlinked`; quitar el filtro de estado del cómputo
de `scheduled_date` tumba sólo
`test_scheduled_date_follows_the_earliest_pending_move`. Volver a
`QuerySet.update` en `_put_in_pack` tumba
`tests/unit/stock/test_stock_picking_packages.py::TestActionPutInPack::test_delegates_to_the_move_lines`.

## Símbolos tocados por archivo

Derivados del AST del diff.

- `addons/project_stock/models/project_project.py`: `pickings_of_type`.
- `addons/purchase_stock/models/stock.py`: `picking_purchase`.
- `addons/stock/models/stock_lot.py`: `_find_delivery_ids_by_lot`.
- `addons/stock/models/stock_move.py`: `_resolve_candidates`.
- `addons/stock/models/stock_move_line.py`: `_compute_location_id`, `_get_aggregated_product_quantities`, `_get_default_dest_location`, `_get_lines_not_entire_pack`, `_get_linkable_moves`, `_get_similar_move_lines`, `_onchange_serial_number`, `_prepare_stock_move_vals`, `_put_in_pack`, `current_picking_first`, `lots_visible`, `picking_location`, `picking_location_dest`, `picking_partner`, `picking_type`, `write`.
- `addons/stock/models/stock_picking.py`: `Meta`, `StockPicking`, `_add_reference`, `_check_entire_pack`, `_check_move_lines_map_quant_package`, `_compute_scheduled_date`, `_compute_state`, `_get_entire_pack_location_dest`, `_get_next_transfers`, `_get_show_allocation`, `_onchange_location_id`, `_onchange_picking_type`, `_remove_reference`, `_send_confirmation_email`, `_set_scheduled_date`, `action_add_entire_packs`, `action_assign`, `action_cancel`, `action_confirm`, `action_detailed_operations`, `action_put_in_pack`, `button_validate`, `calculate_date_category`, `create`, `date_deadline`, `delay_alert_date`, `get_empty_list_help`, `has_scrap_move`, `has_tracking`, `keys_in_groupby`, `lot`, `packages_count`, `picking_type_code`, `picking_type_entire_packs`, `picking_warning_text`, `product`, `reference_ids`, `render_note`, `return_count`, `save`, `show_check_availability`, `show_next_pickings`, `show_operations`, `unlink`, `use_create_lots`, `use_existing_lots`, `warehouse_address`, `write`.
- `addons/stock/models/stock_scrap.py`: `StockScrap`, `_check_company`, `_compute_location_id`, `_compute_scrap_qty`, `_prepare_move_values`, `_unlink_except_done`, `action_get_stock_move_lines`, `do_replenish`, `do_scrap`, `tracking`.

## Lo que este corte no cierra

`_autoconfirm_picking` en `create` sigue divergente (D-8 del docstring de la
clase); `has_deadline_issue`, que la fuente calcula de `scheduled_date`
(`:724-727`), sigue en el grupo bloqueado: sucesor
`stock-picking-deadline-issue-0397`. U5 y U6 siguen en la partición.
