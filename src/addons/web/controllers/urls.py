"""URLs — addons.web (sesión del cliente, ``/api/v2/web/``).

Las rutas conservan el segmento ``session/`` de la referencia
(``odoo19c: addons/web/controllers/session.py``) para que la correspondencia
sea legible sin consultar la tabla del controlador.
"""
from django.urls import path

from addons.web.controllers.session import (
    session_authenticate,
    session_destroy,
    session_info,
    session_logout,
)

app_name = 'web'

urlpatterns = [
    path('session/', session_info, name='session-info'),
    path('session/authenticate/', session_authenticate, name='session-authenticate'),
    path('session/destroy/', session_destroy, name='session-destroy'),
    path('session/logout/', session_logout, name='session-logout'),
]
