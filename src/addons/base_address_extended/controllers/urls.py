"""URLs — consulta pública de código postal (``/api/v2/geo/``)."""
from django.urls import path

from addons.base_address_extended.controllers.main import postal_code_lookup

app_name = 'geo'

urlpatterns = [
    path('postal-codes/<str:postal_code>/', postal_code_lookup,
         name='postal-code-lookup'),
]
