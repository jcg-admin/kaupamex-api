"""
Tests — UC-SYS-03: scan_low_stock task: retirado, la tarea no sobrevivió.

Probaba ``addons.inventory.tasks.scan_low_stock`` (path periódico de alerta
de stock bajo, sobre ``Product``/``ProductVariant``). La familia
``inventory`` se disolvió en ``stock`` (H-API-212 y hermanas) y esta tarea
**no viajó**: verificado, ``stock`` no tiene módulo ``tasks.py``
(``find src/addons/stock -iname tasks.py`` → vacío) y ningún ``grep -rn
"low_stock"`` sobre ``src/addons/`` encuentra un sucesor. El modelo
``StockAlert`` que la tarea alimentaba tampoco tiene equivalente portado.

Mismo patrón de retiro que ``test_cancel_timeout_task.py`` (tarea que no
sobrevivió al disolver su addon dueño): se documenta la ausencia en vez de
dejar un test que referencia un módulo inexistente.
"""
