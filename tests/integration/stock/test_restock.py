"""
Tests — Stock replenishment (restock): retirado (HTTP).

Probaba ``POST /api/v2/admin/inventory/variants/{pk}/restocks/`` (entrada
positiva de stock ligada a una referencia de compra, ``StockMovement`` tipo
``RESTOCK``). El addon ``stock`` no tiene capa REST — ver
``test_stock_dashboard.py`` para la cita completa. ``StockMovement`` tampoco
tiene sucesor portado. El propio módulo se declaraba TDD-RED (*"the RESTOCK
type, the service method, the serializer and the endpoint do not exist
yet"*) — seguía siendo cierto al momento de este retiro, ahora por una razón
distinta (la familia que lo hospedaba se disolvió antes de que el TDD
avanzara a verde).
"""
