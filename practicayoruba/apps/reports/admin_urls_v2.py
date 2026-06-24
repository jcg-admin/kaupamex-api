"""
Admin URLs v2 — apps.reports F5 (§2.9).

Mounted in config/urls.py:
  path('api/v2/admin/', include('apps.reports.admin_urls_v2', namespace='admin_reports_v2'))

POST /api/v2/admin/reports/<slug>/exports/ — Tier A: same view as v1
/admin/reports/<slug>/export/ (trailing noun pluralised).
"""
from django.urls import path

from .views import ReportExportView

app_name = 'admin_reports_v2'

urlpatterns = [
    path('reports/<slug:slug>/exports/',
         ReportExportView.as_view(),
         name='report-export'),
]
