"""
URLs públicas — apps.addons.chartsize
GET /api/v1/catalogue/<slug>/variants/<pk>/  — validación de variante (UC-CHT-02)
"""
from django.urls import path
from .views import VariantDetailView, VariantSingleView

app_name = 'chartsize'

urlpatterns = [
    path('<slug:slug>/variants/<int:pk>/',
         VariantSingleView.as_view(), name='variant-single'),
]
