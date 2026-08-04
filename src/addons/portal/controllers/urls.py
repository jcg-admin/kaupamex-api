"""Rutas del portal de cuenta — ≙ ``/my/*`` de ``odoo19c: portal``."""
from django.urls import path

from addons.portal.controllers.main import (
    PortalAccountView,
    PortalAddressArchiveView,
    PortalAddressListView,
    PortalDeactivationView,
    PortalPasswordView,
    PortalSecurityView,
)

app_name = 'portal'

urlpatterns = [
    path('account/', PortalAccountView.as_view(), name='account'),
    path('addresses/', PortalAddressListView.as_view(), name='addresses'),
    path('addresses/<int:pk>/archive/', PortalAddressArchiveView.as_view(),
         name='address-archive'),
    path('security/', PortalSecurityView.as_view(), name='security'),
    path('security/password/', PortalPasswordView.as_view(), name='password'),
    path('deactivations/', PortalDeactivationView.as_view(),
         name='deactivations'),
]
