"""Tests — Idempotency-Key en checkout (T-603): retirado, sin endpoint HTTP.

Probaba que dos ``POST /api/v2/orders/`` con el mismo header
``Idempotency-Key`` produjeran una sola ``SaleOrder`` y un solo decremento
de stock. El endpoint no existe — ver ``test_checkout.py`` para la cita
completa (``website_sale`` ausente). El propio mecanismo de idempotencia es
HTTP-level (header + cache de respuesta), así que no tiene equivalente a
nivel de servicio que preservar aquí: se retira íntegro y se reescribe
cuando exista la vista real.
"""
