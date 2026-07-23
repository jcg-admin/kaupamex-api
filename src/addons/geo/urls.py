"""URLs de la app geo (SEPOMEX) — consulta pública de CP."""
from django.urls import path

from addons.geo.views import PostalCodeLookupView

urlpatterns = [
    path('postal-codes/<str:postal_code>/', PostalCodeLookupView.as_view(),
         name='postal-code-lookup'),
]
