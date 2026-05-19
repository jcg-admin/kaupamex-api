"""Admin URLs — apps.support (UC-SUPP-05)."""
from django.urls import path

from .views import AdminSupportTicketListView

app_name = 'admin_support'

urlpatterns = [
    path('support/tickets/',
         AdminSupportTicketListView.as_view(),
         name='admin-ticket-list'),
]
