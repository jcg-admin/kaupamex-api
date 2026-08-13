"""URLs del recorrido del comprador sobre su venta.

Montado en ``config/urls.py``::

    path('api/v2/orders/', include(('addons.sale.controllers.urls', 'sale'),
                                   namespace='sale_v2'))

Las rutas conservan el prefijo ``/orders/`` del contrato público aunque el
addon se llame ``sale``: el comprador habla de "mis pedidos", no de "mis
ventas". Es la misma asimetría que la referencia acepta al servir
``/my/orders`` desde el addon ``sale``.
"""
from django.urls import path

from addons.sale.controllers.main import OrderCancelView, OrderDetailView, OrderListView

app_name = 'sale'

urlpatterns = [
    path('', OrderListView.as_view(), name='order-collection'),
    path('<str:order_number>/', OrderDetailView.as_view(), name='order-detail'),
    path('<str:order_number>/cancellations/', OrderCancelView.as_view(),
         name='order-cancellations'),
]
