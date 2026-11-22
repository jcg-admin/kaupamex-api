# U3b — los llamadores de `order.order_line` y el borrado con `self.env`

Fecha: 2026-11-22T21:07:18. Complementa `sale-basemodel-u3b-order.md`
(decisión 2) con la tabla por símbolo que exige `check_reference_flow`, y con
lo que destapó el subconjunto derivado al adoptar la orden.

## Lo que midió el subconjunto, y su arreglo

1. **`BaseModel.unlink` comprobaba el ACL con el entorno ambiente.** Construía
   un `AccessQuerySet` y llamaba a su `check_access`, que lee `is_su()`. La
   fuente llama `self.check_access('unlink')`
   (`odoo19c: odoo/orm/models.py:4203`), que lee `self.env.su`, igual que
   nuestro `write`. Con la orden del carrito entregada con `sudo()` ≙
   `sale_order_sudo` (`odoo19c: addons/website_sale/models/website.py:679`),
   `order.order_line.unlink()` daba 403 en `save_cart_for_later`. Prueba:
   `tests/unit/orm/test_record_env_x2many_and_django_delete.py`
   (`test_unlink_checks_access_in_the_environment_of_the_records`) y
   `tests/integration/test_v2_cart_wishlist_notifications.py`. Anulado,
   caen exactamente esas tres pruebas.
2. **El motor de reportes se prueba elevado.** `orden_con_lineas` de
   `tests/integration/base/test_report_engine.py` entrega `orden.sudo()`: el
   caso mide el motor, y el ACL de `sale.order.line` lo mide
   `tests/unit/sale/test_sale_security_acl.py`.

## Los símbolos que cambian

| Símbolo | Referencia | Prueba |
|---|---|---|
| `SaleOrder._sum_lines` | `odoo19c: addons/sale/models/sale_order.py:513` (`_compute_amounts` recorre `order_line`) | `tests/integration/sale/test_sale_cluster.py` |
| `SaleOrder._compute_has_archived_products` | `odoo19c: addons/sale/models/sale_order.py:345` | `tests/unit/sale/test_sale_order_basemodel.py` (`test_archived_products_are_read_through_the_recordset`) |
| `amount_delivery` (`addons/delivery/models/sale_order.py`) | `odoo19c: addons/delivery/models/sale_order.py:32` (`order_line.filtered('is_delivery')`, `:45`) | `tests/integration/sale/test_amount_sql_paridad_e4.py` |
| `set_delivery_line` | `odoo19c: addons/delivery/models/sale_order.py:54-67` (`_remove_delivery_line` hace `filtered("is_delivery").unlink()`) | `tests/integration/delivery/test_logistics_endpoints.py` |
| `amount_reward` (`addons/sale_loyalty/models/sale_order.py`) | `odoo19c: addons/sale_loyalty/models/sale_order.py:202` (`filtered(lambda l: l.is_reward_line)`) | `tests/integration/sale/test_amount_sql_paridad_e4.py` |
| `set_reward_line` | `odoo19c: addons/sale_loyalty/models/sale_order.py:202` (`filtered(...).unlink()`) | `tests/integration/loyalty/test_vouchers.py` |
| `SaleOrderCoupon.discount_base` | `odoo19c: addons/sale_loyalty/models/sale_order.py:278` (filtra `not x.is_reward_line`) | `tests/unit/sale/test_sale_order_basemodel.py` (`test_the_coupon_base_skips_delivery_and_reward_lines`) |
| `free_shipping_discount` (`addons/sale_loyalty_delivery/models/sale_order.py`) | `odoo19c: addons/sale_loyalty_delivery/models/sale_order.py:32` | `tests/integration/sale/test_grupo_a_sale_addons.py` |
| `SaleOrderDelivery.compute_status` | `odoo19c: addons/sale_stock/models/sale_order.py:91` (`_compute_delivery_status`) | `tests/unit/sale/test_sale_order_basemodel.py` (`test_the_delivery_status_reads_the_line_deliveries`) |
| `_filter_can_send_abandoned_cart_mail` (`addons/website_sale/models/sale_order.py`) | `odoo19c: addons/website_sale/models/sale_order.py:775` | `tests/unit/website_sale/test_abandoned_cart.py` |
| migración `0020_report_saleorder_iterates_recordset` | la plantilla recorre `docs.order_line` sin `.all` (`odoo19c: addons/sale/models/sale_order.py:35`, `order_line` es recordset) | `tests/unit/sale/test_sale_order_basemodel.py` (`test_the_report_template_iterates_the_recordset`) |

En todos el cambio es el mismo: la API de gestor (`.all()`, `.filter`,
`.first()`, `.delete()`) pasa a la de recordset de la fuente (iterar,
`filtered`, `[:1]`, `unlink()`), porque `order.order_line` ya no es gestor.

## El recálculo explícito tras `unlink()` en bloque

Decisión 3 del diseño de U3b: se midió por anulación. Sin las cuatro
llamadas (`clear_draft_items`, la rama de envío gratis de
`set_delivery_line`, y las dos salidas tempranas de `set_reward_line`), el
subconjunto `tests/integration/{delivery,loyalty,sale}`,
`tests/unit/{sale,website_sale}` y
`tests/integration/test_v2_cart_wishlist_notifications.py` dio **698 passed,
0 failed**. La prueba que lee el total tras el borrado es
`test_unlinking_lines_in_bulk_recomputes_the_order`
(`tests/unit/sale/test_sale_order_basemodel.py`), y su mecanismo —la
dependencia de `_compute_amounts` sobre `order_line`— ya se probó por
anulación en U3a. Las cuatro se retiran.

`SaleOrderMatrix.apply` (`addons/sale_product_matrix/`) conserva la suya:
borra con `QuerySet.delete()` de Django, que no pasa por `unlink`.

*Métrica:* pruebas en rojo con las llamadas anuladas.
*Ciega a:* una rama sin prueba que lea el total después del borrado; la
cobertura de la rama de envío gratis y de las salidas tempranas del cupón es
la del mecanismo, no una prueba por rama.
