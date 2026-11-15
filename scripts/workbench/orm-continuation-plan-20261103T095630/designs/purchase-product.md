# purchase: lo que cuelga en product (unidad purchase-product-0397)

Referencia: `odoo19c: addons/purchase/models/product.py` (154 líneas, tres
clases y 15 símbolos).

## Inventario de la fuente y estado de su base en el puerto

| Clase · símbolo | Fuente | Base en el puerto |
|---|---|---|
| template `purchased_product_qty` (calculado) | `:13,30-32` | suma de las variantes |
| template `purchase_method` (calculado, `precompute`, `store`) | `:14-19,22-28` | depende de `type`; existe `ProductTemplate.type` |
| template `purchase_line_warn_msg` | `:20` | campo nuevo |
| template `_get_backend_root_menu_ids` | `:34-35` | **la base no existe** (0 hits) |
| template `get_import_templates` | `:37-45` | existe en otros modelos; en `product.template` no |
| template `action_view_po` | `:47-54` | `ir.actions.actions._for_xml_id` existe; la acción `purchase.action_purchase_history` no está sembrada |
| product `purchased_product_qty` | `:61-62,69-82` | `_read_group` sobre las líneas aprobadas del último año |
| product `is_in_purchase_order` (calculado y con búsqueda) | `:64-67,84-105` | depende de `order_id` en el contexto |
| product `action_view_po` | `:107-111` | lo mismo que en la plantilla |
| product `_get_backend_root_menu_ids` | `:113-114` | la base no existe |
| product `_update_uom` | `:116-131` | la base existe (`stock/models/product.py`) |
| product `_trigger_uom_warning` | `:133-140` | la base existe (`stock/models/product.py`) |
| supplierinfo `_onchange_partner_id` | `:146-148` | lee `property_purchase_currency_id`, que **no existe** |
| supplierinfo `_get_filtered_supplier` | `:150-153` | la base existe (`product_supplierinfo.py`) |

Diferencias de nombre en el puerto que el porte respeta:

- la línea de compra usa `product_qty`, mientras la fuente usa
  `product_uom_qty` para la cantidad en la unidad del producto;
- la plantilla usa `uom`, donde la fuente usa `uom_id`.

## Corte en dos unidades

1. **Esta unidad.** Los campos y los métodos con base:
   - `purchased_product_qty` en las dos clases;
   - `purchase_method`;
   - `purchase_line_warn_msg`, con el aviso de la línea de factura de
     `account_invoice.py:530,556-560`;
   - `is_in_purchase_order` con su búsqueda;
   - `_update_uom` y `_trigger_uom_warning`;
   - `_get_filtered_supplier`.
2. **Sucesora `purchase-product-actions-0397`.** Lo que necesita piezas
   ausentes:
   - `action_view_po` necesita sembrar `purchase.action_purchase_history`;
   - `_get_backend_root_menu_ids` necesita la base en `product` y el menú
     `purchase.menu_purchase_root`;
   - `get_import_templates` necesita la plantilla XLS estática;
   - `_onchange_partner_id` necesita `property_purchase_currency_id` en
     `res.partner`.

## Casos de prueba (RED)

1. Un servicio toma `purchase_method='purchase'` y un consumible toma el
   valor por defecto, `'receive'`.
2. `purchased_product_qty` de la variante suma las líneas de órdenes
   aprobadas en el último año, sin las anteriores ni las de borrador. La
   plantilla suma sus variantes.
3. `is_in_purchase_order` es verdadero sólo para los productos de la orden
   del contexto, y la búsqueda `('is_in_purchase_order', 'in', [True])`
   devuelve esos productos.
4. `_update_uom` rehúsa si alguna línea usa otra unidad y, si no, reescribe
   la unidad de las líneas.
5. `_trigger_uom_warning` es verdadero si el producto tiene líneas de compra.
6. `purchase_line_warn_msg` llega a la línea de factura sólo con el grupo
   `purchase.group_warning_purchase`. Sin el grupo sembrado, sale vacío.
