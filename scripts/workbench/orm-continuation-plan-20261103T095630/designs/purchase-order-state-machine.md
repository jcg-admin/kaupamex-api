# purchase.order: máquina de estados (unidad purchase-order-state-machine-0397)

Referencia: `odoo19c: addons/purchase/models/purchase_order.py` (odoo-tools
`19.x/odoo-19.0`), con las líneas citadas abajo.

## Qué declara la fuente

| Símbolo | Fuente | Estado en el puerto antes de la unidad |
|---|---|---|
| `state`, con 5 valores (`draft`, `sent`, `to approve`, `purchase`, `cancel`) | `:105-111` | 4 valores: falta `to approve` |
| `locked` (Boolean, default False, copy=False) | `:112-116` | ausente |
| `date_approve` (Datetime, readonly, index, copy=False) | `:90` | ausente |
| `lock_confirmed_po` (related `company_id.po_lock`) | `:117` | ausente; `po_lock` ya existe en res.company (unidad purchase-res-company) |
| `user_id` ("Buyer", default `env.user`, index) | `:157-159` | ausente |
| `button_approve(force=False)` | `:615-619` | ausente |
| `button_draft` | `:621-623` | ausente |
| `button_confirm` | `:625-639` | difiere: rehúsa con ValidationError en vez de saltar la orden; exige líneas; no recorre un recordset |
| `button_cancel` | `:641-649` | difiere: no comprueba `locked` |
| `button_lock` / `button_unlock` | `:651-655` | ausentes |
| `_confirmation_error_message` | `:657-668` | ausente |
| `_approval_allowed` | `:1251-1260` | ausente |
| línea `display_type` (Selection section, subsection, note) | `purchase_order_line.py:91-94` | ausente |
| línea `is_downpayment` (Boolean) | `purchase_order_line.py:95` | ausente |

## Lo que porta esta unidad

Todos los campos de la tabla y los ocho métodos, con la forma de la fuente:
los métodos recorren `self` como recordset, `button_confirm` salta (no
rehúsa) la orden que no está en `draft`/`sent` y devuelve `True`, y
`button_cancel` rehúsa con `UserError` si alguna orden está bloqueada.
`_approval_allowed` lee `po_double_validation` y `po_double_validation_amount`
de `res.company`, convierte el importe con `ResCurrency._convert` y cierra
con `has_group('purchase.group_purchase_manager')`.

## Tres llamadas de la fuente que dependen de piezas medidas como ausentes

Cada una queda en el código con su comentario `pendiente:` y una fila en el
plan (TASK-API-0397):

1. **`order.order_line._validate_analytic_distribution()`** (`:631`).
   `analytic_mixin.py:53` registra que `_validate_distribution` depende de
   `get_relevant_plans` y de la columna por plan. Fila del plan:
   `purchase-analytic-validation-0397`.
2. **`order._add_supplier_to_product()`** (`:633`). `product.supplierinfo`
   existe; faltan en la línea `product_uom_id` y `selected_seller_id`, y en la
   orden `_prepare_supplier_info`. Es la unidad que sigue:
   `purchase-add-supplier-to-product-0397`.
3. **La guarda de facturas de `button_cancel`** (`:645-647`). Lee
   `po.invoice_ids`, que en la fuente se calcula desde
   `account.move.line.purchase_line_id`; medido:
   `grep -rn purchase_line_id addons/account/models` da 0. Fila del plan:
   `purchase-invoice-link-0397`.

El grupo `purchase.group_purchase_manager` todavía no está sembrado. Hasta
que lo esté, `has_group` resuelve el xmlid a `None` y devuelve `False`
(`res_users.py:1705-1709`). Así, la tercera rama de `_approval_allowed` es
falsa para todos, igual que para un usuario sin el grupo, que es el resultado
seguro. La siembra pertenece a la seguridad de purchase, descrita en
`purchase-headers-and-security.md`.

## Una divergencia que viene de antes y que esta unidad no amplía

La fuente asigna `name` en `create` desde la secuencia `purchase.order`. El
puerto lo asigna al confirmar con `_generate_purchase_name`. Esta unidad lo
conserva dentro del bucle de `button_confirm` para no romper a sus
consumidores. La secuencia se registra como `purchase-order-sequence-0397`.

## Casos de prueba (RED antes de implementar)

1. `state` acepta `to approve`, y `locked`, `date_approve` y `user_id`
   existen, con `user_id` por defecto igual al usuario en contexto.
2. `po_double_validation='one_step'` hace que `button_confirm` deje
   `purchase` con `date_approve`.
3. `two_step` con un importe mayor o igual al umbral, sin el grupo, deja
   `to approve` y sin `date_approve`.
4. `two_step` por debajo del umbral aprueba.
5. `po_lock='lock'` hace que la orden aprobada quede con `locked=True`.
6. `button_confirm` sobre una orden ya `purchase` no la toca y devuelve `True`.
7. Una línea sin producto, sin `display_type` y sin `is_downpayment` lleva a
   `UserError`. Una línea de sección sin producto no.
8. `button_cancel` sobre una orden bloqueada lleva a `UserError` y no la
   persiste. Después de `button_unlock`, la cancela.
9. `button_draft` devuelve la orden a `draft`.

Anulación: con `_approval_allowed` reducido a `return True` caen los casos 3
y 5-bis (`to approve`). Con la guarda de `locked` retirada cae el caso 8.
