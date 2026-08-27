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
    database_backup,
    database_create,
    database_drop,
    database_duplicate,
    database_list,
    database_restore,
)
from addons.web.controllers.domain import validate as domain_validate
from addons.web.controllers.home import health, robots
from addons.web.controllers.pivot import export_xlsx as pivot_export_xlsx
from addons.web.controllers.vcard import download_vcard
from addons.web.controllers.webmanifest import (
    scoped_app_icon_png,
    scoped_app_manifest,
    webmanifest,
)
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
    path('database/backup/', database_backup, name='database-backup'),
    path('database/restore/', database_restore, name='database-restore'),
    # ≙ binary.py (H-API-369, DEC-FW-04) — streaming de binarios; nombres
    # de ruta calcan el segmento ``/web/...`` de la referencia.
    path('content/', content_common, name='content-common'),
    path('image/', content_image, name='content-image'),
    path('binary/upload_attachment/', upload_attachment, name='binary-upload-attachment'),
    path('binary/company_logo/', company_logo, name='binary-company-logo'),
    # ≙ webmanifest.py — manifiesto PWA y su app acotada. Públicas
    # (``auth='public'`` en la referencia): no exponen nada que
    # ``company_logo``/``robots`` no expongan ya.
    path('manifest.webmanifest', webmanifest, name='webmanifest'),
    path('manifest.scoped_app_manifest', scoped_app_manifest, name='scoped-app-manifest'),
    path('scoped_app_icon_png', scoped_app_icon_png, name='scoped-app-icon-png'),
    # ≙ domain.py (tarea #397) — validación de dominios contra un modelo.
    path('domain/validate/', domain_validate, name='domain-validate'),
    # ≙ pivot.py (tarea #397) — exportación de tabla dinámica a XLSX.
    path('pivot/export_xlsx/', pivot_export_xlsx, name='pivot-export-xlsx'),
    # ≙ vcard.py (tarea #397) — descarga de vCard de uno o varios contactos.
    path('vcard/download/', download_vcard, name='vcard-download'),
]
