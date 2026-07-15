"""URLs admin — apps.authz (superficie del panel, gateada por capacidad).

Se monta en ``/api/v2/admin/`` (ver ``config/urls.py``).
"""
from django.urls import path

from apps.authz.admin_views import (
    AdminPermissionCatalogView, AdminRoleListView, AdminRolePermissionsView,
)

app_name = 'admin_authz'

urlpatterns = [
    path('roles/', AdminRoleListView.as_view(), name='role-list'),
    path('permissions/', AdminPermissionCatalogView.as_view(),
         name='permission-catalog'),
    path('roles/<slug:role_code>/permissions/',
         AdminRolePermissionsView.as_view(), name='role-permissions'),
]
