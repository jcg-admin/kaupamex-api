from django.urls import path
from .views import AdminSupportTicketListView

app_name = 'admin_support_v2'

urlpatterns = [
    path('support/tickets/',
         AdminSupportTicketListView.as_view(),
         name='admin-ticket-list'),
]
