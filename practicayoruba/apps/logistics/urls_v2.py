"""
URLs v2 — apps.logistics F5 (§1.3).

Mounted in config/urls.py:
  path('api/v2/', include('apps.logistics.urls_v2', namespace='logistics_v2'))
"""
from django.urls import path

from .views_v2 import (
    BuyerOrderShipmentV2View,
    ShipmentCancellationV2View,
    ShipmentDeliveryV2View,
    ShipmentDetailV2View,
    ShipmentListCreateV2View,
    ShipmentProblemReportV2View,
)

app_name = 'logistics_v2'

urlpatterns = [
    path('shipments/',
         ShipmentListCreateV2View.as_view(),
         name='shipments'),
    path('shipments/<int:pk>/',
         ShipmentDetailV2View.as_view(),
         name='shipment-detail'),
    path('shipments/<int:pk>/cancellations/',
         ShipmentCancellationV2View.as_view(),
         name='shipment-cancel'),
    path('shipments/<int:pk>/deliveries/',
         ShipmentDeliveryV2View.as_view(),
         name='shipment-deliver'),
    path('orders/<int:order_id>/shipment/',
         BuyerOrderShipmentV2View.as_view(),
         name='order-shipment'),
    path('shipments/<int:pk>/problem-reports/',
         ShipmentProblemReportV2View.as_view(),
         name='shipment-problem-report'),
]
