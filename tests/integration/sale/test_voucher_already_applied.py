"""Tests — VOUCHER_ALREADY_APPLIED 409 en CartVoucherView: retirado.

Probaba ``POST``/``DELETE /api/v2/cart/voucher/`` sobre el carrito HTTP. La
superficie del carrito no existe — ver ``test_cart.py`` para la cita
completa (``website_sale`` ausente). El descuento de cupón sobre el draft
sí existe y sí se prueba a nivel de servicio en
``addons.sale_loyalty``/``addons.sale.services._draft_extra_discount``.
"""
