"""
Admin URLs — apps.catalogue (Sprint 6)
UC-CAT-06: CRUD de categorías para administradores.
Montado en config/urls.py como: path('api/v1/admin/', include('apps.catalogue.admin_urls'))
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryAdminViewSet

app_name = 'admin_catalogue'

router = DefaultRouter()
router.register(r'categories', CategoryAdminViewSet, basename='admin-category')

urlpatterns = [
    path('', include(router.urls)),
]
