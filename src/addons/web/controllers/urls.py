"""URLs — addons.web (sesión del cliente, ``/api/v2/web/``).

Las rutas conservan el segmento ``session/`` de la referencia
(``odoo19c: addons/web/controllers/session.py``) para que la correspondencia
sea legible sin consultar la tabla del controlador.
"""
from django.urls import path

from addons.web.controllers.binary import (
    company_logo,
    content_common,
    content_image,
    upload_attachment,
)
from addons.web.controllers.database import (
    database_create,
    database_drop,
    database_duplicate,
    database_list,
)
from addons.web.controllers.home import health, robots
from addons.web.controllers.session import (
    session_authenticate,
    session_check,
    session_destroy,
    session_get_lang_list,
    session_info,
    session_logout,
    session_modules,
)

app_name = 'web'

urlpatterns = [
    path('session/', session_info, name='session-info'),
    path('session/authenticate/', session_authenticate, name='session-authenticate'),
    path('session/destroy/', session_destroy, name='session-destroy'),
    path('session/logout/', session_logout, name='session-logout'),
    path('session/check/', session_check, name='session-check'),
    path('session/modules/', session_modules, name='session-modules'),
    path('session/get_lang_list/', session_get_lang_list, name='session-get-lang-list'),
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
    # ≙ binary.py (H-API-369, DEC-FW-04) — streaming de binarios; nombres
    # de ruta calcan el segmento ``/web/...`` de la referencia.
    path('content/', content_common, name='content-common'),
    path('image/', content_image, name='content-image'),
    path('binary/upload_attachment/', upload_attachment, name='binary-upload-attachment'),
    path('binary/company_logo/', company_logo, name='binary-company-logo'),
]
