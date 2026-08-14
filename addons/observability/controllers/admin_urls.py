"""
Admin URLs — addons.observability (SOL-011 T-06, logs tecnicos).

Montado en config/urls.py:
  path('api/v2/admin/', include(('addons.observability.controllers.admin_urls', 'admin_core'),
       namespace='admin_core_v2'))

Sirve el endpoint read-only de logs (UC-ADM-06, DEC-LOG-08 revisada). Patron
per-app ``apps/<app>/admin_urls.py`` bajo /api/v2/admin/ (no hay modulo
``apps/admin`` central; ver SOL-016).

Movido desde ``core.admin_urls`` en el slice 5 de
``adoptar-arquitectura-server-service-odoo`` (DEC-10); el namespace
``admin_core_v2`` se conserva sin cambios (contrato de URL intacto).
"""
from django.urls import path

from .main import AdminLogsView

app_name = 'admin_core_v2'

urlpatterns = [
    path('logs/', AdminLogsView.as_view(), name='logs'),
]
