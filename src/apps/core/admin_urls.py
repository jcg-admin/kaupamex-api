"""
Admin URLs — apps.core (SOL-011 T-06, logs tecnicos).

Montado en config/urls.py:
  path('api/v2/admin/', include(('apps.core.admin_urls', 'admin_core'),
       namespace='admin_core_v2'))

Sirve el endpoint read-only de logs (UC-ADM-06, DEC-LOG-08 revisada). Patron
per-app ``apps/<app>/admin_urls.py`` bajo /api/v2/admin/ (no hay modulo
``apps/admin`` central; ver SOL-016).
"""
from django.urls import path

from .admin_views import AdminLogsView

app_name = 'admin_core_v2'

urlpatterns = [
    path('logs/', AdminLogsView.as_view(), name='logs'),
]
