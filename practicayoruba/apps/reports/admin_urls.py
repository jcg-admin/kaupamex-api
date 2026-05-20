"""
Admin URLs — apps.reports

Mounted in config/urls.py:
  path('api/v1/admin/', include('apps.reports.admin_urls', namespace='admin_reports'))

DEC-DOC-005: English identifiers.
"""
from django.urls import path
from .views import CustomersRFMReportView, DashboardReportView, ReportExportView, SalesReportView, TopSellersReportView


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
    # UC-REP-05 export — slug is one of: sales|top-sellers|customers-rfm|dashboard
    path('reports/<slug:slug>/export/',
         ReportExportView.as_view(), name='reports-export'),
]
