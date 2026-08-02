"""Tests — E5/R5: retirado, los proxies del espejo ya no existen.

Este módulo verificaba la equivalencia **antes** del corte: que
``ActiveOrder``/``DeliveredOrder`` (modelos ``proxy=True`` sobre
``orders_order``, el espejo) seleccionaran las mismas filas que sus
reemplazos canónicos (``active_sale_orders()`` / ``filter_orders_by_status``
sobre ``sale.SaleOrder``) — mismo propósito que
``test_carrier_write_through_e5r5.py`` para el campo ``carrier``.

El retiro del addon espejo ``orders`` (SOL-098, ``api@77bd1f0``) le quitó el
lado "proxy" a la comparación: ``ActiveOrder``/``DeliveredOrder`` no existen
(``grep -rn "class ActiveOrder" src/`` y ``grep -rn "class DeliveredOrder" src/``
→ vacíos ambos), y
``make_order`` ya no devuelve un segundo objeto ``.sale_order_id`` que enlazar
— la venta **es** la orden. No queda nada con qué comparar la canónica: los
dos consumidores reales que este módulo protegía
(``settings_app/views.py`` — guard de ``ShippingMethod`` en uso;
``payments/views.py`` — comprador recurrente) ya leen directamente
``SaleOrder.carrier`` / ``SaleOrder.partner`` y ``active_sale_orders()`` /
``filter_orders_by_status``; su cobertura vive en la suite de esos módulos.
"""
