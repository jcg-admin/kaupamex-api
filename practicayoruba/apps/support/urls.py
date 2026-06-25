"""URLs — apps.support (F8 consolidation)."""
from django.urls import path
from .views import (
    SupportTicketCloseView,
    SupportTicketDetailView,
    SupportTicketListCreateView,
    SupportTicketReopenView,
    SupportTicketReplyView,
    SupportTicketStatusV2View,
)


app_name = 'support'

urlpatterns = [
    path('tickets/',
         SupportTicketListCreateView.as_view(),
         name='ticket-list-create'),
    path('tickets/<int:ticket_id>/',
         SupportTicketDetailView.as_view(),
         name='ticket-detail'),
    path('tickets/<int:ticket_id>/replies/',
         SupportTicketReplyView.as_view(),
         name='ticket-replies'),
    path('tickets/<int:ticket_id>/close/',
         SupportTicketCloseView.as_view(),
         name='ticket-close'),
    path('tickets/<int:ticket_id>/reopen/',
         SupportTicketReopenView.as_view(),
         name='ticket-reopen'),
    path('tickets/<int:ticket_id>/status/',
         SupportTicketStatusV2View.as_view(), name='ticket-status'),
]
