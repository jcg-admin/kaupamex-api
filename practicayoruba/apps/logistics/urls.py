"""
URLs — apps.logistics (P-13).
"""
from django.urls import path
from .views import (
    BuyerGuideView, CancelGuideView, ConfirmDeliveryView,
    CourierDetailView, CourierListCreateView, LogisticsPanelView,
    ShipmentGuideDetailView, ShipmentGuideListCreateView,
)

app_name = 'logistics'

urlpatterns = [
    path('',                                    LogisticsPanelView.as_view(),          name='panel'),
    path('couriers/',                           CourierListCreateView.as_view(),       name='couriers'),
    path('couriers/<int:pk>/',                  CourierDetailView.as_view(),           name='courier-detail'),
    path('guides/',                             ShipmentGuideListCreateView.as_view(), name='guides-list-create'),
    path('guides/<int:pk>/',                    ShipmentGuideDetailView.as_view(),     name='guide-detail'),
    path('guides/<int:pk>/cancel/',             CancelGuideView.as_view(),             name='guide-cancel'),
    path('guides/<int:pk>/confirm-delivery/',   ConfirmDeliveryView.as_view(),         name='confirm-delivery'),
    path('buyer/order/<int:order_id>/guide/',   BuyerGuideView.as_view(),              name='buyer-guide'),
]
