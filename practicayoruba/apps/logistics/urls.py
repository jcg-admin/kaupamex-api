"""
URLs — apps.logistics (P-13).

Mounted in config/urls.py as:
  path('api/v1/logistics/', include('apps.logistics.urls', namespace='logistics'))
"""
from django.urls import path

from .views import (
    ConfirmDeliveryView,
    CourierListView,
    LogisticsPanelView,
    ShipmentGuideDetailView,
    ShipmentGuideListCreateView,
)

app_name = 'logistics'

urlpatterns = [
    path('',                                LogisticsPanelView.as_view(),
         name='panel'),
    path('couriers/',                       CourierListView.as_view(),
         name='couriers'),
    path('guides/',                         ShipmentGuideListCreateView.as_view(),
         name='guides-list-create'),
    path('guides/<int:pk>/',                ShipmentGuideDetailView.as_view(),
         name='guide-detail'),
    path('guides/<int:pk>/confirm-delivery/', ConfirmDeliveryView.as_view(),
         name='confirm-delivery'),
]
