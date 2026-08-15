"""``ir.http`` extendido por ``utm`` — la captura de los parámetros en cookie.

Adaptación fiel de Odoo ``utm/models/ir_http.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3). Los 3 símbolos de la fuente están portados.

Es la mitad de **entrada** del addon: cuando alguien llega con
``?utm_campaign=…&utm_source=…&utm_medium=…`` en la URL, el valor se guarda en
una cookie de 31 días. Después, cuando esa persona crea algo (un prospecto,
un pedido), ``utm.mixin.default_get`` lee la cookie y rellena los tres ejes.
Sin esta mitad el mixin no tiene de dónde leer.

Divergencias declaradas:

- ``_inherit = 'ir.http'`` → **subclase de** ``addons.base.models.IrHttp``.
  Aquél es un modelo abstracto de Django, y heredarlo es la forma nativa del
  ``_inherit`` sobre abstracto. No se usa ``extend_model`` porque éste opera
  sobre el registro de apps, donde un modelo abstracto no está.
- ``_post_dispatch`` de la fuente encadena con ``super()._post_dispatch``.
  Aquí **no hay a quién encadenar**: medido, ``src/addons/base/models/ir_http.py``
  declara ``slugify_one``, ``slugify``, ``slug``, ``unslug`` y
  ``sanitize_cookies`` — ningún ``_post_dispatch``. Se conserva el nombre y su
  papel de punto de salida; el encadenado se repone cuando alguien más lo
  declare.
- El **despacho** que invoca ``_post_dispatch`` es, en este stack, un
  middleware WSGI. ``UtmCookieMiddleware`` vive en este mismo archivo, igual
  que ``CompanyContextMiddleware`` vive en el ``ir_http.py`` de ``base`` — el
  precedente del árbol para "el mecanismo de petición que acompaña a
  ``ir.http``".
- ``cookie_type='optional'`` de la fuente es su clasificación de
  consentimiento. Aquí las tres cookies se declaran en ``COOKIE_REGISTER``
  con categoría ``marketing`` (≠ ``necessary``), que es exactamente lo que
  ``optional`` significa: sin consentimiento, ``CookieGovernanceMiddleware``
  las suprime en modo enforce.
"""
from addons.base.models.ir_http import IrHttp as BaseIrHttp

from .utm_mixin import UtmMixin

#: 31 días — ≙ ``max_age=31 * 24 * 3600`` (``odoo19c: ir_http.py:21``).
UTM_COOKIE_MAX_AGE = 31 * 24 * 3600


class IrHttp(BaseIrHttp):
    """``ir.http`` con la captura UTM (``odoo19c: ir_http.py:7-26``)."""

    _inherit = 'ir.http'

    class Meta:
        abstract = True

    @classmethod
    def get_utm_domain_cookies(cls, request):
        """≙ ``get_utm_domain_cookies`` (``odoo19c: :10-12``).

        El dominio con el que se emite la cookie. La fuente lo lee de
        ``request.httprequest.host``, que es una global de su despacho; aquí
        la petición es un argumento porque este stack no la tiene en ambiente.
        """
        return request.get_host()

    @classmethod
    def _set_utm(cls, response, request):
        """≙ ``_set_utm`` (``odoo19c: :14-21``) — pasa los parámetros a cookie.

        Sólo escribe cuando el valor entrante difiere del que ya lleva la
        cookie: sin esa guarda, cada petición reemitiría las tres cookies.

        La fuente empieza con ``Response.load(response)`` para asegurarse de
        que la respuesta es una suya; aquí la respuesta de un middleware de
        Django ya lo es por construcción.
        """
        domain = cls.get_utm_domain_cookies(request)
        for url_parameter, __, cookie_name in UtmMixin.tracking_fields():
            value = request.GET.get(url_parameter) or request.POST.get(url_parameter)
            if value is not None and request.COOKIES.get(cookie_name) != value:
                response.set_cookie(
                    cookie_name, value,
                    max_age=UTM_COOKIE_MAX_AGE, domain=domain,
                )
        return response

    @classmethod
    def _post_dispatch(cls, response, request):
        """≙ ``_post_dispatch`` (``odoo19c: :23-26``) — el punto de salida.

        Sin encadenado a ``super()``: ``base`` no declara ``_post_dispatch``
        (medido — ver el docstring del módulo).
        """
        cls._set_utm(response, request)
        return response


class UtmCookieMiddleware:
    """El despacho que invoca ``_post_dispatch`` en este stack.

    Sitio en ``MIDDLEWARE``: **por encima** de
    ``CookieGovernanceMiddleware``, para que su ``process_response`` (orden
    inverso) corra **antes** que el de aquél y las tres cookies lleguen ya
    puestas al gobierno de consentimiento.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return IrHttp._post_dispatch(response, request)
