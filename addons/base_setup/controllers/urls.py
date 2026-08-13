"""URLs de configuración del sitio — ``base``.

Montado en ``config/urls.py``::

    path('api/v2/config/', include(('addons.base_setup.controllers.urls', 'config'),
                                   namespace='config_v2'))
"""
from django.urls import path

from addons.base_setup.controllers.main import SiteSettingsView

app_name = 'config'

urlpatterns = [
    path('settings/', SiteSettingsView.as_view(), name='site-settings'),
]
