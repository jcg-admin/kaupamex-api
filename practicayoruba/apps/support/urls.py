"""URLs — apps.support."""
from django.urls import path
from .views import SupportTicketCloseView, SupportTicketDetailView, SupportTicketListCreateView, SupportTicketReopenView, SupportTicketReplyView


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
]
