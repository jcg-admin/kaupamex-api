"""Admin URLs — logs técnicos de ``base`` (UC-ADM-06).

Montado en ``config/urls.py``::

    path('api/v2/admin/', include(('addons.base.controllers.admin_urls', 'admin_core'),
         namespace='admin_core_v2'))

Movido desde ``addons.observability.controllers.admin_urls`` con DEC-AF-11, al
disolverse el addon: la vista sirve ``ir.logging``, que es de ``base``. **El
namespace ``admin_core_v2`` y la ruta ``logs/`` se conservan sin cambios** —
el contrato de URL no es parte de la disolución.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_main import AdminLogsView
from .module_catalogue import TechnicalModuleViewSet

app_name = 'admin_core_v2'

module_router = DefaultRouter()
# No añadir una raíz administrativa sin el gate de la vista de recurso.
module_router.include_root_view = False
module_router.register('technical-modules', TechnicalModuleViewSet,
                       basename='technical-module')

urlpatterns = [
    path('logs/', AdminLogsView.as_view(), name='logs'),
    path('', include(module_router.urls)),
]
