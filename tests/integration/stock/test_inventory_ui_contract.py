"""
Tests — Inventory endpoints UC-INV-01..05 (contrato UI): retirado (HTTP).

Probaba el contrato JSON en inglés de ``/api/v2/admin/inventory/`` +
``variants/<id>/movements/`` + ``variants/<id>/adjust/`` + ``import/``. El
addon ``stock`` no tiene capa REST — ver ``test_stock_dashboard.py`` para la
cita completa. Mismo retiro que ``test_stock_adjustments.py`` (incluye el
mismo ``StockMovement`` sin sucesor portado).
"""
