"""Tests — checkout HTTP (UC-ORD-01): retirado, la superficie REST no existe.

Probaba ``POST /api/v2/orders/`` (crear la venta desde el carrito) y
``POST /api/v2/cart/items/`` para poblarlo. Ninguna de las dos rutas existe:
``src/addons/sale/urls.py`` sólo monta ``OrderListView``/``OrderDetailView``/
``OrderCancelView`` (GET/POST-cancelación sobre la venta **ya confirmada**);
el propio módulo lo documenta (``src/addons/sale/views.py:14-16``):
*"POST /api/v2/orders/ (checkout) — su hogar es website_sale, que todavía no
existe en el árbol"*. Verificado: ``find src/addons/website_sale`` → vacío.

El flujo de checkout **sí** existe y **sí** se prueba a nivel de servicio —
``addons.sale.services.confirm_draft_order``, que hace exactamente lo que
este módulo verificaba por HTTP (guards de stock, snapshot de precio
vigente, cupón, dirección de entrega, transición ``draft → sale``) — ver
``test_draft_order.py`` y ``test_sale_order_parity_e1.py``. Cuando
``website_sale`` exponga el endpoint, este módulo se reescribe contra la
vista real.
"""
