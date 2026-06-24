"""URLs v2 — apps.support (F3 migrar-urls-rest-v2)."""
from django.urls import path
from .views import (
    SupportTicketDetailView,
    SupportTicketListCreateView,
    SupportTicketReplyView,
)
from .views_v2 import SupportTicketStatusV2View

app_name = 'support_v2'

urlpatterns = [
    path('tickets/', SupportTicketListCreateView.as_view(), name='ticket-list-create'),
    path('tickets/<int:ticket_id>/', SupportTicketDetailView.as_view(), name='ticket-detail'),
    path('tickets/<int:ticket_id>/replies/', SupportTicketReplyView.as_view(), name='ticket-replies'),
    # Tier B: close/reopen → PATCH status
    path('tickets/<int:ticket_id>/status/', SupportTicketStatusV2View.as_view(), name='ticket-status'),
]
