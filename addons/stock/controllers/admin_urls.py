"""URLs admin del inventario — ``stock``.

Montado en ``config/urls.py``::

    path('api/v2/admin/', include(('addons.stock.controllers.admin_urls',
                                   'admin_inventory'), namespace='admin_inventory_v2'))

Misma convención que ``website``/``rating``/``crm``: lo de back-office cuelga
de ``api/v2/admin/`` y va en su propio módulo.
"""
from django.urls import path

from addons.stock.controllers.main import (
    inventory_alerts,
    inventory_dashboard,
)

app_name = 'admin_inventory'

urlpatterns = [
    path('inventory/', inventory_dashboard, name='inventory-dashboard'),
    path('inventory/alerts/', inventory_alerts, name='inventory-alerts'),
]
