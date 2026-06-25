"""
URLs — apps.logistics (P-13).
"""
from django.urls import path
from .views import (
    BuyerGuideView, BuyerReportIncidentView, CancelGuideView, ConfirmDeliveryView,
    CourierDetailView, CourierListCreateView, LogisticsPanelView,
    ShipmentGuideDetailView, ShipmentGuideListCreateView,
)
from .webhooks import CourierWebhookView

app_name = 'logistics'

urlpatterns = [
    path('',                                    LogisticsPanelView.as_view(),          name='panel'),
    path('couriers/',                           CourierListCreateView.as_view(),       name='couriers'),
    path('couriers/<int:pk>/',                  CourierDetailView.as_view(),           name='courier-detail'),
    path('guides/',                             ShipmentGuideListCreateView.as_view(), name='guides-list-create'),
    path('guides/<int:pk>/',                    ShipmentGuideDetailView.as_view(),     name='guide-detail'),
    path('guides/<int:pk>/cancel/',              CancelGuideView.as_view(),             name='guide-cancel'),
    path('guides/<int:pk>/cancellations/',       CancelGuideView.as_view(),             name='guide-cancellations'),
    path('guides/<int:pk>/confirm-delivery/',   ConfirmDeliveryView.as_view(),         name='confirm-delivery'),
    path('buyer/order/<int:order_id>/guide/',   BuyerGuideView.as_view(),              name='buyer-guide'),
    # UC-LOG-07: el comprador dueño reporta un problema de su envío. Ruta
    # order-scoped consistente con buyer-guide (la propiedad se verifica por
    # Order.user). El contrato del UC (PARTE 7C) menciona
    # /guides/<pk>/incidents/ con auth staff — drift documentado como hallazgo:
    # PARTE 2/6 del UC exigen que el ACTOR sea el comprador dueño, no staff.
    path('buyer/order/<int:order_id>/incident/', BuyerReportIncidentView.as_view(),    name='buyer-report-incident'),
    # LOG-04 (US-1.2 / DEC-LOOP-05): webhook de estado del courier. AllowAny,
    # autenticado por firma HMAC con el secreto compartido del courier.
    path('webhook/courier/',                    CourierWebhookView.as_view(),          name='courier-webhook'),
]
