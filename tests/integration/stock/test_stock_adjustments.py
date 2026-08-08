"""
Tests — Stock restoration, delta adjustments y CSV import: retirado (HTTP).

Probaba ``/api/v2/admin/inventory/`` + ``/imports/`` + hermanas
(UC-INV-03/04/05: restauración idempotente, ajuste manual por delta,
importación CSV). El addon ``stock`` no tiene capa REST — ver
``test_stock_dashboard.py`` para la cita completa (``views.py``/``urls.py``
ausentes). ``StockMovement`` tampoco tiene sucesor portado (el ledger de
movimientos con ``movement_type``/``delta``/``reference`` no viajó de
``inventory`` a ``stock`` — el ``stock.StockMove`` actual sólo modela el
movimiento en tránsito Odoo, sin esos campos de auditoría).

``InventoryService.restore``/``decrement``/``check_availability`` (el núcleo
de UC-INV-02/03 que este módulo ejercía por HTTP) **sí** existe y se prueba
indirectamente en los tests de ``addons.sale.services``
(``confirm_draft_order``/``cancel_order``, ver
``test_sale_order_parity_e1.py``). El ajuste manual (UC-INV-04) y la
importación CSV (UC-INV-05) no tienen sucesor de servicio que ejercer sin
la capa REST — quedan retirados hasta que ``stock`` la reciba.
"""
