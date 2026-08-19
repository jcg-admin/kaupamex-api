r"""``product.replenish`` — el asistente de reabastecimiento que compra:
NO PORTADO.

Adaptación de Odoo ``purchase_stock/wizard/product_replenish.py``
(``odoo19c: addons/purchase_stock/wizard/product_replenish.py``, 101 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué hace en la fuente: el asistente «reabastecer este producto» aprende a
comprar. Gana el selector de proveedor, suma el plazo de entrega del proveedor
más los días para comprar de la empresa a la fecha prevista, y ofrece la ruta
de compra entre las elegibles.

Los 9 símbolos, con su bloqueo medido
======================================

*Métrica:* entradas del cuerpo de ``class ProductReplenish`` contadas por AST
sobre la fuente. Son **10** con ``_inherit``; **9** sin él, los nueve métodos,
cero campos.

.. code-block:: text

    grep -rn "product.replenish" addons/ src/ --include=*.py   → 2

Los **dos** hits son menciones en prosa que declaran esta misma ausencia:
``addons/stock/models/stock_replenish_mixin.py:106`` (*«El asistente
``product.replenish`` de la referencia no está portado»*) y el docstring de
``models/product.py`` de este addon. **Cero declaraciones de clase.**

Los nueve métodos se agrupan en tres causas:

1. **Encadenan un ``super()`` del asistente base** — ``default_get``
   (``:10-26``), ``_compute_date_planned`` (``:35-40``),
   ``_prepare_run_values`` (``:42-47``), ``_get_record_to_notify``
   (``:65-67``), ``_get_replenishment_order_notification_link`` (``:69-75``),
   ``_get_date_planned`` (``:77-89``) y ``_get_route_domain`` (``:91-101``).
   Sin la clase base no hay eslabón anterior (``H-API-733``).
2. **Son eventos del formulario** — ``_onchange_supplier_id`` (``:28-33``) es
   ``@api.onchange``: lo dispara el cliente web al cambiar la ruta.
3. **Devuelven un descriptor de acción** — ``action_stock_replenishment_info``
   (``:49-63``) crea un punto de pedido y abre otro asistente que tampoco
   existe (ver ``stock_replenishment_info.py``).

Lo que SÍ quedó listo para cuando el asistente llegue
=======================================================

Tres de las piezas que estos métodos consumen **se portan en este mismo pase**,
y conviene que quien retome el asistente no las vuelva a buscar:

- ``StockWarehouseOrderpoint.supplier`` — ``models/stock.py`` de este addon
  (lo leen ``default_get`` ``:24-25`` y ``action_stock_replenishment_info``).
- ``StockReplenishMixin.show_vendor`` / ``_get_show_vendor`` —
  ``models/stock_replenish_mixin.py`` (lo lee ``_onchange_supplier_id``
  ``:30``).
- ``ResCompany.days_to_purchase`` — ``models/res_company.py`` (lo suma
  ``_get_date_planned`` ``:87``).

Es decir: el bloqueo es **la clase del asistente**, no sus dependencias. Cuando
``stock`` porte ``product.replenish``, estas 101 líneas se portan sin
decisiones nuevas salvo las dos ya conocidas — el ``@api.onchange`` se vuelve
método normal y la URL del descriptor apunta al recurso de este stack (mismo
criterio que D-4 de ``models/stock.py``).

Sucesor
========

El porte de ``product.replenish`` pertenece a ``stock``. Su ausencia ya está
declarada allá (``addons/stock/models/stock_replenish_mixin.py:104-107``) con
la **tarea #330**; este archivo es su contraparte de compras.
"""
