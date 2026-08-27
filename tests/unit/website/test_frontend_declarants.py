"""Los DECLARANTES de ``is_frontend`` en las vistas públicas (tarea #550).

El MECANISMO ya está probado en
``tests/unit/base/test_ir_http_frontend_flag.py``: el middleware estampa
``request.is_frontend`` desde la declaración de la vista despachada
(≙ ``odoo19c: addons/http_routing/models/ir_http.py:375`` —
``request.is_frontend = routing.get('website', False)``). Aquí se prueba la
otra mitad: que cada vista de cara pública **declara** el flag, y que la
superficie admin **no** lo lleva. Cada declarante cita en su comentario la
ruta de la referencia con ``website=True`` que lo respalda.

Sin base de datos: sólo importa las clases y lee su atributo.
"""
import pytest

from addons.base.models.ir_http import CompanyContextMiddleware
from addons.portal.controllers.main import (
    PortalAccountView,
    PortalAddressArchiveView,
    PortalAddressListView,
    PortalDeactivationView,
    PortalPasswordView,
    PortalSecurityView,
)
from addons.website.controllers.main import (
    PublicStaticPageView,
    StaticPageAdminDetailView,
    StaticPageAdminListView,
    StaticPageRestorationV2View,
    StaticPageStatusV2View,
)

#: Vistas de cara pública — su contraparte en la referencia declara
#: ``website=True`` en su ``@http.route`` (cita ``file:line`` junto a cada
#: declaración en el archivo de la vista).
FRONTEND_DECLARANTS = [
    PortalAccountView,          # odoo19c: portal/controllers/portal.py:190
    PortalAddressListView,      # odoo19c: portal/controllers/portal.py:219
    PortalAddressArchiveView,   # odoo19c: portal/controllers/portal.py:858
    PortalSecurityView,         # odoo19c: portal/controllers/portal.py:871
    PortalPasswordView,         # odoo19c: portal/controllers/portal.py:871
    PortalDeactivationView,     # odoo19c: portal/controllers/portal.py:914
    PublicStaticPageView,       # odoo19c: website/controllers/main.py:344
]

#: Superficie admin representativa — la referencia la sirve con el web
#: client, no con rutas ``website=True``; NO debe llevar el flag.
ADMIN_VIEWS = [
    StaticPageAdminListView,
    StaticPageAdminDetailView,
    StaticPageStatusV2View,
    StaticPageRestorationV2View,
]


@pytest.mark.parametrize('view_class', FRONTEND_DECLARANTS)
def test_public_view_declares_frontend(view_class):
    # DRF expone la clase como ``view.cls``; el middleware lee el atributo
    # sobre la clase, así que la declaración se asserta ahí.
    assert getattr(view_class, 'is_frontend', False) is True


@pytest.mark.parametrize('view_class', ADMIN_VIEWS)
def test_admin_view_does_not_declare_frontend(view_class):
    # El default de la referencia es False
    # (``odoo19c: addons/http_routing/__init__.py:11``); una vista admin no
    # lo promueve.
    assert getattr(view_class, 'is_frontend', False) is False


@pytest.mark.parametrize('view_class', FRONTEND_DECLARANTS)
def test_middleware_reads_the_declaration_through_as_view(view_class):
    # Cierre del circuito declarante→mecanismo: la vista real, envuelta por
    # ``as_view()`` como la despacha Django, es leída por el mismo helper
    # que consume el middleware.
    view_func = view_class.as_view()
    assert CompanyContextMiddleware._view_declares_frontend(view_func) is True


def test_admin_view_is_backend_through_as_view():
    view_func = StaticPageAdminListView.as_view()
    assert CompanyContextMiddleware._view_declares_frontend(view_func) is False
