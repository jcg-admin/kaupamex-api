# purchase: el vínculo con las facturas (unidad purchase-invoice-link-0397)

Referencia: `odoo19c: addons/purchase/models/account_invoice.py:523-560`,
`purchase_order.py:70-75,125-126,641-649` y `purchase_order_line.py:56`.

## Qué declara la fuente

| Símbolo | Fuente |
|---|---|
| `account.move.line.purchase_line_id`: Many2one, `ondelete='set null'`, `index='btree_not_null'`, `copy=False` | `account_invoice.py:528` |
| `account.move.line.purchase_order_id`: related `purchase_line_id.order_id` | `:529` |
| `account.move.line.is_downpayment` | `:527` |
| `account.move.line.purchase_line_warn_msg`, calculado | `:530,557-...` |
| `_copy_data_extend_business_fields`, que copia `purchase_line_id` | `:532-535` |
| `purchase.order.line.invoice_lines`, el One2many inverso | `purchase_order_line.py:56` |
| `purchase.order.invoice_ids`: Many2many calculado y almacenado, más `invoice_count` | `purchase_order.py:70-75,125-126` |
| la guarda de facturas de `button_cancel` | `:645-647` |

## Mecanismo

- `account.move.line` es un modelo de `account`. `purchase` le cuelga los
  campos con `extend_model('account', 'AccountMoveLine', campos=...)` desde
  su `AppConfig.ready()`. La migración vive en `account` y depende de la
  migración de `purchase` que crea `purchaseorderline`. Es el precedente de
  `fleet.0004`, que depende de `hr` para su FK a `hr.hremployee`.
- `invoice_lines` es el `related_name` de `purchase_line_id`.
- `invoice_ids` almacenado y calculado: el precedente de Many2many
  calculado y almacenado es `base_automation.py:467,473`. Se mide que el
  cómputo dispare con `order_line.invoice_lines.move_id`, como en la fuente.

## Por medir antes de RED

- `purchase_line_warn_msg` lee `purchase.group_warning_purchase` y el aviso
  del producto. El grupo no está sembrado, igual que
  `group_purchase_manager`. Se porta con la misma resolución que
  `_approval_allowed`.
- `_copy_data_extend_business_fields`: existe en el `account.move.line` del
  puerto, o hay que portarlo antes.

## Casos de prueba (RED)

1. Una línea de factura con `purchase_line_id` aparece en `invoice_lines` de
   la línea de compra, y su `purchase_order_id` es la orden.
2. `invoice_ids` y `invoice_count` de la orden reflejan las facturas de sus
   líneas, y cambian cuando una línea de factura cambia de factura.
3. `button_cancel` rehúsa con `UserError` si alguna factura no está en
   `cancel` ni en `draft`, y cancela si todas están en borrador.
4. Borrar la línea de compra deja `purchase_line_id` en NULL
   (`ondelete='set null'`).
