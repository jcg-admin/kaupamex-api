"""
Rutas de la API v2 — apps.support (rutas del comprador)

Registradas en config/urls.py bajo api/v2/support/.
Mismas vistas que v1.
"""
from django.urls import path
from .views import (
    SupportTicketListCreateView,
    SupportTicketDetailView,
    SupportTicketReplyView,
    SupportTicketCloseView,
    SupportTicketReopenView,
)

app_name = 'support_v2'

urlpatterns = [
    path('tickets/',
         SupportTicketListCreateView.as_view(),
         name='ticket-list-create'),
    path('tickets/<int:ticket_id>/replies/',
         SupportTicketReplyView.as_view(),
         name='ticket-replies'),
    path('tickets/<int:ticket_id>/close/',
         SupportTicketCloseView.as_view(),
         name='ticket-close'),
    path('tickets/<int:ticket_id>/reopen/',
         SupportTicketReopenView.as_view(),
         name='ticket-reopen'),
    path('tickets/<int:ticket_id>/',
         SupportTicketDetailView.as_view(),
         name='ticket-detail'),
]
