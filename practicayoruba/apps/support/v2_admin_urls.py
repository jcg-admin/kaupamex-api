"""
Rutas de la API v2 — apps.support (rutas de administración)

Registradas en config/urls.py bajo api/v2/admin/.
Mismas vistas que v1.
"""
from django.urls import path
from .views import AdminSupportTicketListView

app_name = 'admin_support_v2'

urlpatterns = [
    path('support/tickets/',
         AdminSupportTicketListView.as_view(),
         name='admin-ticket-list'),
]
