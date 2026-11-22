# U3c — guardas de borrado, tarifa y restricciones de `sale`

Fecha: 2026-11-22T22:01:43. Sucesor declarado por
`sale-basemodel-u3b-order.md` (`sale-unlink-guards-and-constraints-0397`).
Orden y línea ya son `BaseModel` (U3a, U3b), así que `unlink` corre las
comprobaciones `@api.ondelete` (`_run_ondelete_checks`, ≙
`odoo19c: odoo/orm/models.py:4205-4208`).

## Premisa medida antes de diseñar

`_check_line_unlink` lee `line.state`. En la fuente es
`related='order_id.state', store=True, precompute=True`
(`odoo19c: addons/sale/models/sale_order_line.py:56-59`). Aquí es un
`Selection` suelto que **nada sincroniza**: `action_confirm` y `action_cancel`
escriben `order.state` y la línea conserva el valor con que nació. Portar la
guarda sin el related daría una guarda que nunca dispara. Por eso U3c tiene
dos tramos y el primero es la premisa del segundo.

Lo mismo pasa con `company_id`, `currency_id`, `order_partner_id` y
`salesman_id` de la línea (Many2one related de la orden). El motor admite
`related=..., store=True` para un `Selection` en un `BaseModel` (precedente:
`parent_state` de `addons/account/models/account_move_line.py:76`), pero los
Many2one related almacenados se resuelven hoy en `save()` en todo el árbol
(`account_reconcile_model.py:360`, `account_tax_repartition_line.py:17`):
no hay precedente del motor. Esos cuatro quedan fuera, con sucesor
`sale-line-related-many2one-0397`, a medir aparte.

## Tramo 1 — `state` de la línea como related almacenado

| Símbolo | Referencia | Prueba |
|---|---|---|
| `SaleOrderLine.state` `related='order.state', store=True` | `odoo19c: addons/sale/models/sale_order_line.py:56-59` | `tests/unit/sale/test_sale_guards_u3c.py` (`test_the_line_state_follows_its_order`) |

## Tramo 2 — guardas y restricciones

| Símbolo | Referencia | Prueba |
|---|---|---|
| `SaleOrder._unlink_except_draft_or_cancel` | `odoo19c: addons/sale/models/sale_order.py:1032-1038` | `test_a_confirmed_order_cannot_be_unlinked`, `test_a_draft_order_can_be_unlinked` |
| `SaleOrder.write` (tarifa de una orden confirmada) | `odoo19c: addons/sale/models/sale_order.py:1040-1043` | `test_the_pricelist_of_a_confirmed_order_cannot_change` |
| `SaleOrder._check_prepayment_percent` | `odoo19c: addons/sale/models/sale_order.py:865-869` | `test_prepayment_must_be_a_valid_percentage` |
| `SaleOrder._check_order_line_company_id` | `odoo19c: addons/sale/models/sale_order.py:848-863` | `test_lines_cannot_sell_products_of_another_company` |
| `SaleOrderLine._check_line_unlink` | `odoo19c: addons/sale/models/sale_order_line.py:1452-1467` | `test_confirmed_lines_are_not_unlinkable_except_sections` |
| `SaleOrderLine._unlink_except_confirmed` | `odoo19c: addons/sale/models/sale_order_line.py:1469-1473` | `test_a_confirmed_line_cannot_be_unlinked` |
| `SaleOrderLine._check_combo_item_id` | `odoo19c: addons/sale/models/sale_order_line.py:1293-1305` | `test_a_combo_item_must_belong_to_the_linked_combo` |

Mensajes de error: el texto de la fuente, traducido con `_()` como el resto
de `sale` (`redaccion-tecnica-es.md`); la condición es la de la fuente, sin
recorte.

## Fuera de U3c, declarado

- `create` con secuencia: hoy el nombre lo da `_next_sale_name()` como
  default de campo, sin `company_id` ni `date_order`
  (`odoo19c: addons/sale/models/sale_order.py:1004-1013` usa
  `with_company(...)` y `sequence_date`). Es otra unidad:
  `sale-order-create-sequence-0397`.
- Los cuatro Many2one related de la línea (arriba).

*Métrica:* cada guarda se prueba por anulación: retirada, cae exactamente su
prueba.
*Ciega a:* los borrados que no pasan por `unlink` (un `QuerySet.delete()` de
Django salta `@api.ondelete` salvo que el colector lo invoque: se mide en el
tramo 2, no se supone).
