# purchase.order: el nombre sale de la secuencia al crear (unidad purchase-order-sequence-0397)

Referencia: `odoo19c: addons/purchase/models/purchase_order.py:394-406`, y la
secuencia `seq_purchase_order` de `purchase/data/purchase_data.xml:21-27`:
`code='purchase.order'`, prefijo `P`, relleno 5 y sin empresa.

## Qué hace la fuente

`name` es obligatorio y vale `'New'` por defecto. En `create`, si el nombre
es `'New'`, se toma `ir.sequence.next_by_code('purchase.order',
sequence_date=...)`, con la fecha de `date_order` cuando viene en los valores,
o `'/'` si no hay secuencia. La empresa de los valores se activa
(`with_company`) para que la secuencia de esa empresa gane a la global.

## Estado antes de la unidad

`name` tiene `default=''`, y `button_confirm` lo asigna con
`_generate_purchase_name()`, que da `P-<uuid8>`: un nombre que no es de la
fuente y que nace al confirmar, no al crear.

## Lo que porta

- `name` lleva `default='New'`.
- `create` asigna el nombre de la secuencia cuando el nombre es `'New'`, con
  la empresa de los valores y la fecha de `date_order`.
- Si la secuencia no existe se siembra en el punto de uso, igual que
  `sale.order` (`api: addons/sale/models/sale_order.py:44-60`). Los datos XML
  de la fuente no se cargan en este árbol (H-API-22).
- Se retiran `_generate_purchase_name` y su llamada en `button_confirm`.

## Casos de prueba (RED)

1. Una orden nueva se llama `P00001`, con el relleno de la fuente, y la
   siguiente `P00002`.
2. Un nombre explícito se respeta.
3. Confirmar no cambia el nombre.
4. Con dos secuencias del mismo código, una de la empresa de la orden y una
   global, gana la de la empresa.
