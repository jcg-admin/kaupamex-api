"""Tests — la zona de envío ya no bloquea el checkout: retirado, sin endpoint HTTP.

Ejercía ``POST /api/v2/orders/`` (checkout) tras poblar el carrito con
``POST /api/v2/cart/items/``. Ninguna ruta existe — ver ``test_checkout.py``
para la cita completa (``website_sale`` ausente,
``src/addons/sale/views.py:14-16``). La política que este módulo protegía
(un C.P. no cubierto no rechaza la venta; el costo de envío sale del
``ShippingMethod`` elegido, no de la zona) vive en ``addons.delivery`` y se
reescribe contra la vista real de ``website_sale`` cuando exista.
"""
