"""Tests — carrito HTTP: retirado, la superficie REST no existe.

Este módulo probaba ``/api/v2/cart/`` y hermanas (``items/``, ``snapshots/``,
``merges/``): alta, edición, borrado, guardar-para-después y merge de
carrito anónimo→autenticado (UC-CART-01/02/03/05/06). La familia ``cart`` se
disolvió en ``sale`` (el carrito **es** un ``sale.SaleOrder`` con
``state='draft'`` — ver ``src/addons/sale/services.py``), y el addon
``sale`` sólo restauró la superficie de **consulta/cancelación** de la venta
ya confirmada (``OrderListView``/``OrderDetailView``/``OrderCancelView``,
``src/addons/sale/urls.py``). El propio módulo documenta la ausencia
(``src/addons/sale/views.py:14-16``): *"POST /api/v2/orders/ (checkout) — su
hogar es website_sale, que todavía no existe en el árbol"*; el carrito HTTP
depende del mismo addon ausente.

Verificado: ``find src/addons/website_sale`` → vacío (ningún archivo);
ningún ``urls.py`` del árbol registra una ruta ``cart`` (``grep -rli cart``
sobre los ``urls.py`` de ``src/addons`` → vacío).

La lógica de negocio del carrito **sí** existe y **sí** se prueba — a nivel
de servicio, no de HTTP — en ``addons.sale.services``
(``add_item_to_draft``, ``update_draft_item_quantity``, ``remove_draft_item``,
``clear_draft_items``, ``merge_draft_orders``, ``get_draft_totals``,
``confirm_draft_order``); ver ``test_draft_order.py`` y
``test_sale_order_parity_e1.py``. Cuando ``website_sale`` se cree, este
módulo se reescribe contra sus vistas reales — no antes.

``SavedCart`` (UC-CART-05, guardar para después) no tiene sucesor portado en
absoluto: ``grep -rn "class SavedCart" src/`` → vacío. Su cobertura queda
retirada por completo, no sólo su HTTP.
"""
