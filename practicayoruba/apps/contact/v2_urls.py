"""
Rutas de la API v2 — apps.contact (rutas públicas)

Registradas en config/urls.py bajo api/v2/contact/.
Mismas vistas que v1.
"""
from django.urls import path
from .views import ContactMessageCreateView

app_name = 'contact_v2'

urlpatterns = [
    path('messages/',
         ContactMessageCreateView.as_view(),
         name='create'),
]
