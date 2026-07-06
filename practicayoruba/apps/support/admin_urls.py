from django.urls import path
from .views import AdminSupportTicketExportCSVView, AdminSupportTicketListView

app_name = 'admin_support_v2'

urlpatterns = [
    path('support/tickets/',
         AdminSupportTicketListView.as_view(),
         name='admin-ticket-list'),
    path('support/tickets/export/',
         AdminSupportTicketExportCSVView.as_view(),
         name='admin-ticket-export-csv'),
]
