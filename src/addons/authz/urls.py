"""URLs — addons.authz (superficie del usuario autenticado)."""
from django.urls import path

from addons.authz.views import MyCapabilitiesView, MyMenuView, ReauthSessionView

urlpatterns = [
    path('me/capabilities/', MyCapabilitiesView.as_view(), name='my-capabilities'),
    path('me/menu/', MyMenuView.as_view(), name='my-menu'),
    # DEC-12 — re-autenticación para acciones sensibles: abrir/cerrar/estado.
    path('reauth/', ReauthSessionView.as_view(), name='authz-reauth'),
]
