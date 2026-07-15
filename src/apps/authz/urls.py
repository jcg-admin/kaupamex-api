"""URLs — apps.authz (superficie del usuario autenticado)."""
from django.urls import path

from apps.authz.views import MyCapabilitiesView, MyMenuView

urlpatterns = [
    path('me/capabilities/', MyCapabilitiesView.as_view(), name='my-capabilities'),
    path('me/menu/', MyMenuView.as_view(), name='my-menu'),
]
