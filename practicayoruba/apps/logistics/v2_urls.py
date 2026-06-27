"""
Rutas de la API v2 — apps.logistics (rutas no-webhook)

Registradas en config/urls.py bajo api/v2/logistics/.
DEC-V2-02: el webhook /api/v1/logistics/webhook/* permanece en v1
SIEMPRE — nunca se migra a v2.
"""
from django.urls import path
from .views import (
    BuyerGuideView,
    BuyerReportIncidentView,
    CancelGuideView,
    ConfirmDeliveryView,
    CourierDetailView,
    CourierListCreateView,
    LogisticsPanelView,
    ShipmentGuideDetailView,
    ShipmentGuideListCreateView,
)

app_name = 'logistics_v2'

urlpatterns = [
    path('',
         LogisticsPanelView.as_view(),              name='panel'),
    path('couriers/',
         CourierListCreateView.as_view(),            name='couriers'),
    path('couriers/<int:pk>/',
         CourierDetailView.as_view(),                name='courier-detail'),
    path('guides/',
         ShipmentGuideListCreateView.as_view(),      name='guides-list-create'),
    path('guides/<int:pk>/cancel/',
         CancelGuideView.as_view(),                  name='guide-cancel'),
    path('guides/<int:pk>/confirm-delivery/',
         ConfirmDeliveryView.as_view(),              name='confirm-delivery'),
    path('guides/<int:pk>/',
         ShipmentGuideDetailView.as_view(),          name='guide-detail'),
    path('buyer/order/<int:order_id>/guide/',
         BuyerGuideView.as_view(),                   name='buyer-guide'),
    path('buyer/order/<int:order_id>/incident/',
         BuyerReportIncidentView.as_view(),          name='buyer-report-incident'),
    # webhook/courier/ is intentionally absent — stays on v1 per DEC-V2-02
]
