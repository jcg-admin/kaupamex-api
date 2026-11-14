# purchase.order y purchase.order.line: cabecera y BaseModel

Subunidad 1 de `designs/purchase-headers-and-security.md`. Unidad del plan:
`purchase-order-header-0397` (TASK-API-0397).

## Contrato medido en la referencia

`odoo19c: addons/purchase/models/purchase_order.py`:

| Símbolo | Línea | Aquí antes | Aquí después |
|---|---|---|---|
| clase sobre `models.Model` | :21 | `TimeStampedModel` | `models.BaseModel, MailThread, MailActivityMixin, TimeStampedModel` |
| `_name` | :22 | ausente: el registro no lo conocía | `'purchase.order'` |
| `_inherit` | :23 | ausente | `mail.thread` y `mail.activity.mixin` por herencia; las otras tres, bloqueadas (abajo) |
| `_description` | :24 | ausente | `"Purchase Order"` |
| `_rec_names_search` | :25 | ausente | `['name', 'partner_ref']` |
| `_order` | :26 | `Meta.ordering = ['-create_date', '-id']` | `'priority desc, id desc'` y su `Meta.ordering` |
| `priority` | :78-79 | ausente | `Selection('0' Normal, '1' Urgent)`, default `'0'`, indexado |
| `partner_ref` | :83-87 | ausente | `Char('Vendor Reference')`, `copy=False` |

`purchase_order_line.py`:

| Símbolo | Línea | Aquí antes | Aquí después |
|---|---|---|---|
| clase sobre `models.Model` | :13 | `TimeStampedModel` | `models.BaseModel, TimeStampedModel` |
| `_name` / `_description` / `_order` | :14-17 | ausentes | verbatim |
| `_inherit = ['analytic.mixin']` | :15 | ausente | bloqueado (abajo) |
| `sequence` | :22 | ausente | `Integer`, default `10` |

## Lo que esta subunidad no porta, con su razón

Sólo `portal.mixin` es un bloqueo: no existe. Las otras tres existen y
lo que falta es la dependencia o el hogar; quedan como trabajo pendiente
de la subunidad siguiente, no como bloqueo.

- `portal.mixin`: no existe en este árbol.
- `product.catalog.mixin`: vive en `stock`
  (`addons/stock/models/product_catalog_mixin.py`) y no en `product`, su
  hogar en la fuente; `purchase` no depende de `stock`.
- `account.document.import.mixin`: vive en `account`, y `purchase` no
  declara esa dependencia aquí, aunque la fuente sí.
- `analytic.mixin` de la línea: exige la dependencia de `analytic`.

Las cuatro van a la subunidad `purchase-order-mixins-0397`, que arregla
antes el hogar de `product.catalog.mixin` y las dependencias del manifiesto.

## Casos (RED)

1. `purchase.order` está en el registro, deriva de `BaseModel` y declara
   `_description`, `_rec_names_search` y `_order` de la fuente;
2. hereda `MailThread` y `MailActivityMixin`;
3. `purchase.order.line` igual, con su `_order`;
4. `priority` y `partner_ref` como en la fuente;
5. la línea tiene `sequence` con default 10;
6. las órdenes salen por prioridad y después por id descendente.

## Anulación

- volver a `Meta.ordering = ['-create_date', '-id']`: cae el caso 6;
- retirar `_name` de la orden: caen los casos 1, 2, 4 y 6.
