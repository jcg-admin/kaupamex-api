"""
URLs V2 — apps.chartsize

F1: /api/v2/products/<slug>/variants/<pk>/ (mounted at api/v2/products/).
Variant detail endpoint unchanged from v1; only the URL namespace changes.
"""
from django.urls import path
from .views import VariantSingleView

app_name = 'chartsize_v2'

urlpatterns = [
    path('<slug:slug>/variants/<int:pk>/', VariantSingleView.as_view(), name='variant-single'),
]
