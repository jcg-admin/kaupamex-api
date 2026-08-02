"""
Tests — señal order_created en checkout (T-508, DEC-BC-19): retirado.

Verificaba que ``POST /api/v2/orders/`` (tras poblar el carrito con
``POST /api/v2/cart/items/``) disparara ``order_created`` exactamente una
vez, con ``order.order_number == order.sale_order.name``. Ninguna de las dos
rutas HTTP existe — ver ``test_checkout.py`` para la cita completa
(``website_sale`` ausente) — y el par ``order_number``/``sale_order`` (la
dualidad espejo/canónica) tampoco: la venta **es** la orden desde el retiro
del addon ``orders`` (SOL-098, ``api@77bd1f0`` — ver
``test_identity_sale_name_i1.py``). Duplica el propósito de
``test_order_signal.py`` (mismo caso, mismo retiro).
"""
