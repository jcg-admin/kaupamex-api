# purchase.order: _add_supplier_to_product (unidad purchase-add-supplier-to-product-0397)

Referencia: `odoo19c: addons/purchase/models/purchase_order.py:670-707` y
`purchase_order_line.py:36,96,266-278,753-758`.

## Qué hace la fuente

Al confirmar, por cada línea con producto, añade el proveedor a
`seller_ids` de la plantilla si no lo tiene ya y si la plantilla tiene 10
proveedores o menos:

- El proveedor es la empresa del contacto (`partner_id.parent_id`) cuando la
  orden va a un contacto. Cuentan como «ya proveedor» tanto la empresa como
  el contacto.
- El precio se convierte a la unidad de la plantilla si la línea usa otra
  (`product_uom_id._compute_price(price, default_uom)`).
- `_prepare_supplier_info(partner, line, price, currency)` arma la fila:
  la secuencia es la máxima existente más 1, `min_qty` vale 1, `delay` vale
  0, y el descuento sale de la línea.
- Si la línea tiene `selected_seller_id`, se copian `product_name`,
  `product_code` y la unidad de la línea.
- La escritura se hace con `sudo()`, sin depender de los permisos de quien
  confirma.

## Piezas medidas

| Pieza | Estado |
|---|---|
| `product.supplierinfo` y `seller_ids` (`addons/product/models/product_supplierinfo.py:116,250`) | existe. Modelo de Django, con FK `partner` en lugar de `partner_id` |
| `product.product._select_seller` (`product_product.py:569`) | existe, con la firma de la fuente |
| `uom.uom` (`addons/uom/models/uom_uom.py:106`) | existe; publica `compute_price` y `compute_quantity`, y la fuente declara `_compute_price` y `_compute_quantity` (`odoo19c: uom_uom.py:147,196`). Es el defecto de despromoción (H-API-581): 54 llamadas en 11 archivos |
| línea `product_uom_id` (`purchase_order_line.py:36`) | ausente |
| línea `selected_seller_id`, calculado (`:96,266-278`) y `_get_select_sellers_params` (`:753-758`) | ausente |
| línea `discount` | existe |

## Orden de trabajo

1. Si la renombración de `uom.uom` a `_compute_price` y `_compute_quantity`
   cabe en esta unidad (54 llamadas), la hago aquí. Si no, la registro como
   su propia fila antes de usarla.
2. Línea: `product_uom_id` (Many2one a `uom.Uom`, `on_delete=PROTECT`),
   `selected_seller_id` calculado no almacenado y
   `_get_select_sellers_params`.
3. Orden: `_prepare_supplier_info` y `_add_supplier_to_product`, con su
   llamada en `button_confirm` en lugar de la nota `pendiente:`.

## Casos de prueba (RED antes de implementar)

1. Al confirmar, el proveedor nuevo queda en `seller_ids` con el precio, la
   secuencia máxima existente más 1, `min_qty` en 1 y el descuento de la
   línea.
2. Con un contacto, la fila se crea sobre la empresa.
3. Un proveedor que ya está no se duplica.
4. Con más de 10 proveedores no se añade nada.
5. Una unidad distinta a la de la plantilla convierte el precio.
6. Con `selected_seller_id` se copian `product_name` y `product_code`.

## Medido al implementar

- **La rama de `selected_seller_id` no se alcanza por el flujo de la propia
  fuente.** `_get_filtered_sellers` sólo deja tarifas del contacto o de su
  empresa (`odoo19c: product/models/product_product.py:1040`), y esas dos
  ya son `already_seller` (`purchase_order.py:689`). La alcanza un addon que
  redefine la selección; la prueba la alcanza redefiniendo el cómputo. La
  rama se porta igual: es un símbolo de la fuente con un consumidor
  posible.
- `_prepare_supplier_info` devuelve los nombres de `product.supplierinfo`
  de este árbol (`partner`, `currency`). El modelo es de Django y sus FK no
  llevan el sufijo `_id`.
- Anulación. Cada mitad retirada tumba exactamente su caso:
  - la rama de `selected_seller_id` tumba el caso del nombre y el código;
  - la empresa del contacto tumba el caso del contacto;
  - el tope de 10 tumba el caso de los once proveedores.
