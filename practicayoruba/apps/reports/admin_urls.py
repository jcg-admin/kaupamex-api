"""
Admin URLs — apps.reports

Mounted in config/urls.py:
  path('api/v1/admin/', include('apps.reports.admin_urls', namespace='admin_reports'))

DEC-DOC-005: English identifiers.
"""
from django.urls import path
from .views import CatalogByCategoryReportView, CatalogSummaryReportView, CustomersRFMReportView, DashboardReportView, LowStockReportView, ReportExportView, SalesReportView, TopSellersReportView


app_name = 'admin_reports'

urlpatterns = [
    path('reports/sales/',
         SalesReportView.as_view(), name='reports-sales'),
    path('reports/top-sellers/',
         TopSellersReportView.as_view(), name='reports-top-sellers'),
    path('reports/dashboard/',
         DashboardReportView.as_view(), name='reports-dashboard'),
    path('reports/customers-rfm/',
         CustomersRFMReportView.as_view(), name='reports-customers-rfm'),
    # UC-DB-RPT-01/02/03 — SP-backed (implementar-endpoints-db-rpt sucesora)
    path('reports/catalog-by-category/',
         CatalogByCategoryReportView.as_view(),
         name='reports-catalog-by-category'),
    path('reports/low-stock/',
         LowStockReportView.as_view(), name='reports-low-stock'),
    path('reports/catalog-summary/',
         CatalogSummaryReportView.as_view(),
         name='reports-catalog-summary'),
    # UC-REP-05 export — slug is one of: sales|top-sellers|customers-rfm|dashboard
    # NOTE: catch-all <slug:slug>/export/ debe ir DESPUES de los paths
    # especificos arriba (DEC-DBR-02 — paths SP especificos preceden).
    path('reports/<slug:slug>/export/',
         ReportExportView.as_view(), name='reports-export'),
]
