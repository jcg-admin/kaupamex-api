"""Tests — cookie httpOnly del carrito anónimo: retirado (H-CART-01 Fase 2).

Probaba ``/api/v2/cart/`` + ``/api/v2/cart/items/`` (fijado de la cookie
``cart_token``, durabilidad entre "recargas", exención del
``CookieGovernanceMiddleware``). La superficie HTTP del carrito no existe —
ver ``test_cart.py`` para la cita completa (``website_sale`` ausente,
``src/addons/sale/views.py:14-16``). Mismo motivo de retiro, mismo hueco.
"""
