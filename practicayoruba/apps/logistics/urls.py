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
    # DEC-V2-02: webhook/courier/ stays on v1 per webhook_urls.py
]
