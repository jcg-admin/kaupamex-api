"""URLs de configuración del sitio — ``base``.

Montado en ``config/urls.py``::

    path('api/v2/config/', include(('addons.base_setup.controllers.urls', 'config'),
                                   namespace='config_v2'))
"""
from django.urls import path

from addons.base_setup.controllers.main import (
    BaseSetupDataView,
    BaseSetupDemoActiveView,
    SiteSettingsView,
)

app_name = 'config'

urlpatterns = [
    path('settings/', SiteSettingsView.as_view(), name='site-settings'),
    # ≙ ``/base_setup/data`` (``odoo19c: controllers/main.py:10``) — la ruta
    # se adapta al prefijo REST del addon; el nombre conserva su sentido.
    path('base-setup-data/', BaseSetupDataView.as_view(),
         name='base-setup-data'),
    # ≙ ``/base_setup/demo_active`` (``odoo19c: :53``).
    path('demo-active/', BaseSetupDemoActiveView.as_view(),
         name='base-setup-demo-active'),
]
