"""
URLs — apps.addons.logistics.

Mounted in config/urls.py:
  path('api/v2/',          include(('apps.addons.logistics.urls', 'logistics'),
                                   namespace='logistics_v2'))
  path('api/v1/logistics/', include('apps.addons.logistics.webhook_urls'))
"""
from django.urls import path

from .views import (
    AdminOrderGuideView,
    BuyerGuideView,
    BuyerGuideByNumberView,
    BuyerOrderShipmentV2View,
    BuyerReportIncidentView,
    CancelGuideView,
    ConfirmDeliveryView,
    CourierDetailView,
    CourierListCreateView,
    LogisticsPanelView,
    ShipmentCancellationV2View,
    ShipmentDeliveryV2View,
    ShipmentDetailV2View,
    ShipmentGuideDetailView,
    ShipmentGuideListCreateView,
    ShipmentListCreateV2View,
    ShipmentOffersView,
    ShipmentProblemReportV2View,
)

app_name = 'logistics'

urlpatterns = [
    # v2 canonical shipment API (F5 §1.3)
    path('shipments/',
         ShipmentListCreateV2View.as_view(),
         name='shipments'),
    path('shipping-offers/',
         ShipmentOffersView.as_view(),
         name='shipping-offers'),
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

    # Admin & buyer logistics panel (formerly mounted via passthrough)
    path('logistics/',
         LogisticsPanelView.as_view(),
         name='panel'),
    path('logistics/couriers/',
         CourierListCreateView.as_view(),
         name='couriers'),
    path('logistics/couriers/<int:pk>/',
         CourierDetailView.as_view(),
         name='courier-detail'),
    path('logistics/guides/',
         ShipmentGuideListCreateView.as_view(),
         name='guides-list-create'),
    path('logistics/guides/<int:pk>/',
         ShipmentGuideDetailView.as_view(),
         name='guide-detail'),
    path('logistics/admin/orders/<str:order_number>/guide/',
         AdminOrderGuideView.as_view(),
         name='admin-order-guide'),
    path('logistics/guides/<int:pk>/cancel/',
         CancelGuideView.as_view(),
         name='guide-cancel'),
    path('logistics/guides/<int:pk>/cancellations/',
         CancelGuideView.as_view(),
         name='guide-cancellations'),
    path('logistics/guides/<int:pk>/confirm-delivery/',
         ConfirmDeliveryView.as_view(),
         name='confirm-delivery'),
    path('logistics/buyer/order/<int:order_id>/guide/',
         BuyerGuideView.as_view(),
         name='buyer-guide'),
    # Variante por order_number (identificador público que conoce la UI).
    path('logistics/buyer/orders/<str:order_number>/guide/',
         BuyerGuideByNumberView.as_view(),
         name='buyer-guide-by-number'),
    path('logistics/buyer/order/<int:order_id>/incident/',
         BuyerReportIncidentView.as_view(),
         name='buyer-report-incident'),
    path('logistics/buyer/orders/<str:order_number>/incident/',
         BuyerReportIncidentView.as_view(),
         name='buyer-report-incident-by-number'),
]
