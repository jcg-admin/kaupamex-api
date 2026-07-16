"""
Admin URLs — apps.addons.chartsize (Sprint 9)
Rutas manuales para evitar dependencia de drf-nested-routers.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductVariantAdminViewSet, VariantTypeAdminViewSet, VariantPriceAdminView

app_name = 'admin_chartsize'

# Usamos prefijo products/<product_pk>/ directamente sin nested router
# El ViewSet extrae product_pk del kwargs en _get_product()
variant_router = DefaultRouter()
variant_router.register(
    r'(?P<product_pk>[^/.]+)/variants',
    ProductVariantAdminViewSet,
    basename='admin-variant',
)

vtype_router = DefaultRouter()
vtype_router.register(
    r'(?P<product_pk>[^/.]+)/variant-types',
    VariantTypeAdminViewSet,
    basename='admin-variant-type',
)

urlpatterns = [
    path('products/', include(variant_router.urls)),
    path('products/', include(vtype_router.urls)),
    # UC-CHT-04 — differentiated price endpoint consumed by UI
    path(
        'variants/<int:variant_pk>/price/',
        VariantPriceAdminView.as_view(http_method_names=['get', 'put', 'patch', 'delete', 'head', 'options']),
        name='admin-variant-price',
    ),
]
