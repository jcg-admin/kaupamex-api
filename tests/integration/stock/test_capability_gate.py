"""
Tests — Inventory capability gate (positive + negative granular path): retirado.

Probaba ``GET /api/v2/admin/inventory/`` bajo la capacidad
``inventory.manage``. El addon ``stock`` no tiene capa REST en absoluto —
ver ``test_stock_dashboard.py`` para la cita completa (``views.py``/
``urls.py`` ausentes bajo ``src/addons/stock/``). No hay vista que gatear
todavía; el candado de capacidad se reescribe junto con la vista cuando
``stock`` reciba su superficie admin.
"""
