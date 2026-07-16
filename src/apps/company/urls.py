"""Platform URLs — apps.company (consola L0 del operador Kaupamex)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.company.views import CompanyViewSet

app_name = 'company'

router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='platform-company')

urlpatterns = [path('', include(router.urls))]
