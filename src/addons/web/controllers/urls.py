"""URLs — addons.web (sesión del cliente, ``/api/v2/web/``).

Las rutas conservan el segmento ``session/`` de la referencia
(``odoo19c: addons/web/controllers/session.py``) para que la correspondencia
sea legible sin consultar la tabla del controlador.
"""
from django.urls import path

from addons.web.controllers.database import (
    database_create,
    database_drop,
    database_duplicate,
    database_list,
)
from addons.web.controllers.home import health, robots
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
    # ≙ home.py — infra HTTP genérica, sin dependencia del shell webclient.
    # Montaje bajo el namespace propio del addon; el montaje real de
    # ``robots.txt`` en la raíz del sitio (``/robots.txt``) es trabajo de
    # consolidación en ``config/urls.py`` (ver docstring de home.py).
    path('health/', health, name='web-health'),
    path('robots.txt', robots, name='web-robots'),
    # ≙ database.py — administración de bases company_<N>_db (platform.provision).
    path('database/', database_list, name='database-list'),
    path('database/create/', database_create, name='database-create'),
    path('database/duplicate/', database_duplicate, name='database-duplicate'),
    path('database/drop/', database_drop, name='database-drop'),
]
