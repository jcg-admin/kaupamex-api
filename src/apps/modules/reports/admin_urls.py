"""
Admin URLs — apps.modules.reports (F8 consolidation).

Mounted in config/urls.py:
  path('api/v1/admin/', include('apps.modules.reports.admin_urls', namespace='admin_reports'))

DEC-DOC-005: English identifiers.
"""
from django.urls import path
from .views import CatalogByCategoryReportView, CatalogSummaryReportView, CustomersRFMReportView, DashboardReportView, ExportDownloadView, ExportJobStatusView, LowStockReportView, ReportExportView, SalesReportView, TopSellersReportView


app_name = 'admin_reports_v2'

urlpatterns = [
    path('reports/sales/',
         SalesReportView.as_view(), name='reports-sales'),
    path('reports/top-sellers/',
         TopSellersReportView.as_view(), name='reports-top-sellers'),
    path('reports/dashboard/',
         DashboardReportView.as_view(), name='reports-dashboard'),
    path('reports/customers-rfm/',
         CustomersRFMReportView.as_view(), name='reports-customers-rfm'),
    path('reports/catalog-by-category/',
         CatalogByCategoryReportView.as_view(),
         name='reports-catalog-by-category'),
    path('reports/low-stock/',
         LowStockReportView.as_view(), name='reports-low-stock'),
    path('reports/catalog-summary/',
         CatalogSummaryReportView.as_view(),
         name='reports-catalog-summary'),
    path('reports/export/jobs/<int:job_id>/',
         ExportJobStatusView.as_view(), name='reports-export-job'),
    path('reports/export/download/<str:token>/',
         ExportDownloadView.as_view(), name='reports-export-download'),
    path('reports/<slug:slug>/exports/',
         ReportExportView.as_view(), name='report-exports'),
    path('reports/<slug:slug>/export/',
         ReportExportView.as_view(), name='reports-export'),
]
