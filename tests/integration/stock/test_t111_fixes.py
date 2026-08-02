"""
Tests — T-111 fixes: admin-inventory-dashboard gaps: retirado (HTTP).

Probaba ``/api/v2/admin/inventory/variants/{pk}/`` y
``/api/v2/admin/inventory/{pk}/`` (auditoría ``stock_before``/``reason``,
filtro DESCONTINUADO, referencia de checkout en ``StockMovement``, umbral en
el dashboard). El addon ``stock`` no tiene capa REST — ver
``test_stock_dashboard.py`` para la cita completa. ``StockMovement``
tampoco tiene sucesor portado.
"""
