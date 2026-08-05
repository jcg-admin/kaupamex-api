"""URLs admin — addons.authz (superficie del panel, gateada por capacidad).

Se monta en ``/api/v2/admin/`` (ver ``config/urls.py``).
"""
from django.urls import path

from addons.authz.controllers.admin_main import (
    AdminPermissionCatalogView, AdminRoleListView, AdminRolePermissionsView,
    AdminUserPermissionsView,
)

app_name = 'admin_authz'

urlpatterns = [
    path('users/<int:pk>/permissions/', AdminUserPermissionsView.as_view(),
         name='user-permissions'),
    path('roles/', AdminRoleListView.as_view(), name='role-list'),
    path('permissions/', AdminPermissionCatalogView.as_view(),
         name='permission-catalog'),
    path('roles/<slug:role_code>/permissions/',
         AdminRolePermissionsView.as_view(), name='role-permissions'),
]
