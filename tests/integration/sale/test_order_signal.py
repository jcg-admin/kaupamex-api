"""Tests — señal order_created en checkout (T-508): retirado, sin endpoint HTTP.

Verificaba que ``POST /api/v2/orders/`` disparara la señal ``order_created``
exactamente una vez. El endpoint no existe — ver ``test_checkout.py`` para
la cita completa (``website_sale`` ausente). El punto de emisión canónico
hoy es ``addons.sale.services.confirm_draft_order`` (vía
``order_confirmed.send(...)``, ver el servicio); la señal en sí y sus
receptores se prueban indirectamente en ``test_draft_order.py``.
"""
