"""
URLs públicas — apps.chartsize
GET /api/v1/catalogue/<slug>/variants/<pk>/  — validación de variante (UC-CHT-02)
"""
from django.urls import path
from .views import VariantDetailView

app_name = 'chartsize'

urlpatterns = [
    path('<slug:slug>/variants/<int:pk>/',
         VariantDetailView.as_view(), name='variant-detail'),
]
