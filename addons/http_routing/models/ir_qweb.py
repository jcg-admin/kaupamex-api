"""``ir.qweb`` extendido por ``http_routing`` — el slug dentro de la plantilla.

Adaptación de ``odoo19c: addons/http_routing/models/ir_qweb.py`` (53 líneas,
LGPL-3). **3 símbolos en la fuente** (la constante ``BAD_REQUEST`` y los dos
métodos de ``IrQweb``), **3 portados, 0 ausentes**.

Qué hace: publica en el entorno de la plantilla los nombres que su autor usa
para construir enlaces — ``slug``, ``unslug_url`` y, sólo en una página de
sitio, ``url_for`` y ``url_localized``. Es la razón por la que una plantilla
escribe ``slug(product)`` en vez de recomponer ``<nombre>-<id>`` a mano, que
es exactamente el defecto que este addon cierra del lado de Python.

Qué pieza de este stack cubre cada delegación de la fuente
==========================================================

===============================  =====================================
Fuente delega en                 Aquí lo cubre
===============================  =====================================
``lxml`` (parsear el XML de la   nada en este archivo — este entorno se
plantilla, XPath, herencia de    **construye** y se entrega; quien lo
vistas)                          consume es el compilador de
                                 ``base.IrTemplateExpressions``, que sí
                                 usa ``lxml`` y declara en su docstring
                                 qué compila y qué no
render del HTML                  **React**, en ``kaupamex-ui`` — por eso
                                 ``IrTemplateExpressions.render``
                                 levanta por diseño
el ``request`` global de su      ``get_current_request()`` de
despacho                         ``base.ir_http`` (``ContextVar``)
servir la respuesta              **gunicorn**; el contrato del endpoint
                                 lo fija **DRF**, no una plantilla
===============================  =====================================

Divergencias declaradas
=======================

- ``_inherit = 'ir.qweb'`` → ``chain_method`` sobre
  ``base.IrTemplateExpressions`` (``_name = 'ir.qweb'``, clase llana). Ver su
  docstring: la clase no pasa por ``ModelBase`` porque un modelo sin columnas
  no lo necesita, y sus métodos reciben ``self``.
- La fuente encadena con ``super()._prepare_environment(values)``. Medido::

      grep -c "def _prepare_environment" src/addons/base/models/ir_template_expressions.py
      -> 0

  No hay a quién encadenar: ``base`` **no declara** el método (su archivo lo
  menciona una vez, en prosa, al listar los dos enganches que Enterprise 19
  usa — de ahí que un ``grep`` sin ``def`` dé 1 y no 0; la cita lleva el
  ``def`` justamente por eso). ``chain_method`` instala el método tal cual y
  encadenará solo el día que ``base`` lo declare.
- ``request.is_frontend``: la fuente avisa con ``BAD_REQUEST`` cuando el
  atributo falta habiendo petición. Aquí ``CompanyContextMiddleware`` lo
  estampa en toda petición que pase por él, así que el aviso sólo puede
  dispararlo un camino que fabrique su propio ``HttpRequest`` sin middleware
  —un ``RequestFactory`` en un test, un comando de consola—. Se conserva la
  constante y la guarda: su valor está en que el aviso nombre la salida.
"""
import logging

from addons.base.models.ir_http import IrHttp, get_current_request
from addons.base.models.ir_template_expressions import IrTemplateExpressions
from orm.method_chain import chain_method, wrap_method

_logger = logging.getLogger(__name__)

#: ≙ ``BAD_REQUEST`` (``odoo19c: :8-32``). Se conserva el texto de la fuente
#: adaptado al nombre de las piezas de este árbol: describe una invariante que
#: sigue valiendo —quien renderice una plantilla de sitio debe llegar con la
#: petición marcada— y su valor está en que el aviso nombre la salida.
BAD_REQUEST = """Falta el atributo request.is_frontend.

Hay una petición en curso y no lleva `is_frontend`. Con `http_routing`
instalado, TODA petición debería pasar por `CompanyContextMiddleware` (que
estampa el default) y por `ir.http._match` (que lo decide desde la vista
despachada). Una petición sin la marca suele venir de un camino que fabrica su
propio `HttpRequest` sin pasar por el middleware.

Deben cumplirse estas expectativas:

Cuando:
* hay una petición HTTP en curso
* el registro de modelos está cargado
* `http_routing` está instalado

Entonces:
* request.is_frontend está fijado

Incumplirlo lleva a problemas aguas abajo, por ejemplo aquí dentro del
`ir.qweb` de http_routing. La salida es envolver la petición entrante para
ocultarla mientras se renderiza.
"""


def _prepare_environment(self, previous, values):
    """≙ ``_prepare_environment`` (``odoo19c: :37-48``).

    ``previous`` es el ``super()._prepare_environment(values)`` de la fuente
    (``:38``): se invoca **primero** y lo que devuelve es lo que se devuelve —
    por eso va por :func:`orm.method_chain.wrap_method` y no por
    ``chain_method``, cuyo relevo descartaría la base al recibir ``self``.

    Publica ``slug`` y ``unslug_url`` para toda plantilla, y delega en
    :func:`_prepare_frontend_environment` cuando la petición es de sitio.

    ``IrHttp._slug`` se resuelve al llamar, no al importar: cuando este módulo
    se importa, ``apply_http_routing_extensions`` todavía no ha colgado el
    método sobre la clase.
    """
    qweb = previous(values)
    values['slug'] = IrHttp._slug
    values['unslug_url'] = IrHttp._unslug_url

    request = get_current_request()
    if not values.get('minimal_qcontext') and request is not None:
        if not hasattr(request, 'is_frontend'):
            _logger.warning(BAD_REQUEST, stack_info=True)
        elif request.is_frontend:
            return qweb._prepare_frontend_environment(values)

    return qweb


def _prepare_frontend_environment(self, values):
    """≙ ``_prepare_frontend_environment`` (``odoo19c: :50-53``).

    Los dos nombres que sólo tienen sentido en una página de sitio: construir
    una URL con el idioma puesto, y su variante localizada.
    """
    values['url_for'] = IrHttp._url_for
    values['url_localized'] = IrHttp._url_localized
    return self


def apply_ir_qweb_extensions():
    """Cuelga los dos métodos sobre ``base.IrTemplateExpressions`` — ≙ ``_inherit``.

    ``_prepare_environment`` va con la previa en la mano (la fuente llama a
    ``super()`` primero); ``_prepare_frontend_environment`` no llama a
    ``super()`` en la fuente (``:50-53``), así que el relevo de
    ``chain_method`` reproduce exactamente eso.
    """
    wrap_method(IrTemplateExpressions, '_prepare_environment',
                _prepare_environment)
    chain_method(IrTemplateExpressions, '_prepare_frontend_environment',
                 _prepare_frontend_environment)
