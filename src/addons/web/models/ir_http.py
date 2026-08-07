"""``ir.http`` extendido por ``web`` — detección de bots, cookie de compañías
y bootstrap de sesión del cliente.

Adaptación de ``odoo19c: addons/web/models/ir_http.py``
(``odoo-tools@622ddc2a``, 205 líneas, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). Extiende ``ir.http`` (ya portado en
``base/models/ir_http.py``, H-API-369) con lo específico del **cliente web**:
detección de tráfico de bot, saneo de la cookie de compañías activas, el
ciclo de "debug mode" del webclient servido por el propio backend, y los
payloads de sesión con los que ese cliente arranca.

Completa el addon ``web`` contra H-API-369 / DEC-FW-04 (junto con
``models.py`` y ``base_document_layout.py``, que ya cubrían el resto de la
capa de modelos).

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``,
mismo criterio que ``porte-completo-no-parcial.md``): **11** métodos de
**1** clase (``IrHttp``; ``bots`` es atributo, no cuenta en los 11). **1
portado** (adaptado), **10 declarados ausentes** con razón — no hay recorte
silencioso.

Portado (1)
===========

``is_a_bot`` — algoritmo puro (una cadena user-agent contra una lista de
substrings), sin dependencia de infraestructura ausente. Único cambio de
firma: la referencia lo lee de ``request.httprequest.user_agent.string`` (el
proxy global de petición de Odoo); aquí no existe ese proxy —
``base/models/ir_http.py`` ya declaró todo el enrutado/despacho fuera de esta
adaptación—, así que recibe la cadena por parámetro. Es la misma decisión que
``IrHttp.slugify``/``slug``/``unslug`` ya tomaron: mismo algoritmo, la
petición HTTP entra por parámetro en vez de por estado implícito.

Ausentes (10) — con razón, agrupados por causa
================================================

**1. ``_sanitize_cookies`` — cookie ``cids`` de compañías activas.**
Este árbol NO selecciona compañía por cookie: ``CompanyContextMiddleware``
(``base/models/ir_http.py:216-263``, cableado en
``config/settings/base.py:183``) la fija en cada petición desde
``request.user`` — vía ``ResUsers._permitted_company_ids`` (≙
``_get_company_ids``) — y la limpia en el ``finally``. Sin cookie de
compañías que leer, no hay qué sanear. La extensión de ``base`` a la que esta
override llamaría con ``super()`` (``base/models/ir_http.py::sanitize_cookies``)
ya es un punto de extensión vacío por diseño; portar aquí una segunda función
igualmente vacía no aportaría nada que el mecanismo de ``chain_method`` no
resuelva ya cuando (si alguna vez) haga falta.

**2-4. ``_handle_debug`` / ``_pre_dispatch`` / ``_post_logout`` — hooks del
ciclo de despacho de Werkzeug.** Activan/leen el "debug mode" de sesión
(servir JS sin minificar, cargar assets de test) en cada petición
(``_pre_dispatch``) y limpian la cookie ``cids`` al cerrar sesión
(``_post_logout``). ``base/models/ir_http.py`` (docstring, sección "Qué NO se
porta") ya excluyó **todo** el enrutado y despacho —
``_generate_routing_rules``, ``_match``, ``_pre_dispatch``, ``_dispatch``,
``_post_dispatch``— por ser responsabilidad de Django (URLconf + middleware +
DRF), no de este modelo. Estos tres son ese mismo ciclo, visto desde el lado
del logout/pre-request: sin dispatcher de Werkzeug que instrumentar, no hay
hook que colgar. ``_post_logout`` además depende de la cookie ``cids`` del
punto 1, doblemente ausente.

**5-7. ``webclient_rendering_context`` / ``color_scheme`` / ``lazy_session_info``
— bootstrap del shell JS servido por el propio backend (QWeb).**
``controllers/home.py`` (H-API-369) ya midió la causa raíz de esta familia:
**0** directorios ``static/`` en los 78 addons, **0** renderizado de página
completa por plantilla — el SPA (``kaupamex-ui``, React) lo compila Webpack y
lo sirve Apache (``config/urls.py:199-242``, ``serve_spa``), no Django. Sin
shell que arranque el propio backend, no hay contexto de render que
construir, ni tema de color que decidir server-side, ni sesión "perezosa"
que precargar antes del primer render.

**8. ``session_info`` — YA PORTADO, en la capa DRF, no en el modelo.**
``controllers/session.py::_session_info(user)`` documenta explícitamente
"≙ ``ir.http.session_info()`` de la referencia, recortado a lo publicado" y
enumera campo por campo qué queda fuera (versión de servidor, módulos
instalados, config del webclient) y por qué (sin consumidor en un cliente
REST). No se duplica aquí: un modelo y un controlador construyendo el mismo
payload de sesión por separado divergirían con el primer cambio que sólo
tocara uno de los dos. La arquitectura de este árbol reparte lo que en la
referencia es un único modelo ``ir.http`` entre Django (enrutado/auth, ya
excluido arriba) y DRF (bootstrap de sesión, en ``controllers/session.py``) —
ninguna de las dos mitades es un modelo Django.

**9. ``get_frontend_session_info`` — misma familia que el punto 8, y además
bloqueado campo por campo.** Es la variante pública/anónima de
``session_info``. Sin endpoint que la consuma: el visitante anónimo de este
árbol no arranca con un payload de sesión — el carrito de invitado se
identifica por cabecera (``X-Cart-Token``, DEC-BC-07 de ``kaupamex-ui``), no
por un dict de bootstrap. Y de sus 12 campos, la mayoría no tiene análogo
aquí: ``registry_hash`` (versión del *registry* de módulos de Odoo — sin
registro dinámico de módulos en este ORM), ``profile_session``/
``profile_collectors``/``profile_params`` (perfilado leído de la sesión de
Werkzeug — ``IrProfile`` existe como modelo pero no hay sesión de servidor
que los almacene), ``show_effect`` (parámetro de configuración
``base_setup.show_effect``, sin análogo declarado), ``currencies`` (ver punto
10) y ``quick_login``/``bundle_params.lang`` (leen sesión de Werkzeug sin
contraparte). Portar un dict con más ausencias que presencias no es "hacer lo
que hace el de la referencia" (``porte-completo-no-parcial.md``) — sería un
stub que aparenta cobertura.

**10. ``get_currencies`` — shim ``@api.deprecated`` bloqueado en cascada.**
Reenvía a ``self.env['res.currency'].get_all_currencies()``, que
``base/models/res_currency.py`` (docstring, sección de ausencias) ya declaró
ausente: "caché de listado para el selector de divisa del formulario Odoo —
sin análogo de formulario aquí". Portar el shim llamaría a un método que no
existe en este árbol — no cuenta como portado, cuenta como una llamada rota.
La propia referencia ya lo marca obsoleto desde 19.0 a favor del método de
``res.currency``, así que no hay superficie propia que perder al declararlo
ausente.
"""
from orm.method_chain import chain_method

from addons.base.models.ir_http import IrHttp

#: Substrings de user-agent que identifican tráfico de bot/crawler/preview —
#: verbatim de la referencia (``odoo19c: web/models/ir_http.py:30``).
BOTS = [
    "bot", "crawl", "slurp", "spider", "curl", "wget",
    "facebookexternalhit", "whatsapp", "trendsmapresolver", "pinterest",
    "instagram", "google-pagerenderer", "preview",
]


def is_a_bot(cls, user_agent):
    """≙ ``is_a_bot`` (``odoo19c: web/models/ir_http.py:32-37``).

    La referencia no usa regexp ni normalización Unicode "voluntariamente"
    (su propio comentario) — el mismo criterio se preserva aquí: comparación
    de substrings sobre la cadena en minúsculas.

    :param user_agent: la cadena ``User-Agent`` de la petición (p. ej.
        ``request.META.get('HTTP_USER_AGENT', '')`` en una vista Django).
        La referencia la lee de ``request.httprequest.user_agent.string``, el
        proxy global de petición que este árbol no tiene — ver el docstring
        del módulo.
    """
    ua = (user_agent or '').lower()
    return any(bot in ua for bot in cls.bots)


def apply_web_extensions():
    """Cuelga la detección de bots sobre ``base.IrHttp`` — ≙ ``_inherit``.

    ``bots`` es un atributo (campo), no un método: se asigna directamente,
    sin pasar por ``chain_method`` — la guarda que ``chain_method``
    resuelve (dos addons que overridean el MISMO método) no aplica a listas
    de datos (``orm/method_chain.py``, "correcta para campos").

    ``is_a_bot`` se instala como ``classmethod`` para preservar la misma
    convención de llamada que ya usan los demás utilitarios de ``IrHttp``
    (``IrHttp.slugify_one(value)`` — ver su consumidor en
    ``addons/website_sale_wishlist/controllers/serializers.py``): se llama
    por la clase, no por instancia, porque ``IrHttp`` es abstracto y nunca se
    instancia.

    Se invoca desde ``WebConfig.ready()``, cuando el registro de modelos ya
    está poblado y ``setattr`` sobre ``base.IrHttp`` no rompe con
    ``AppRegistryNotReady``.
    """
    IrHttp.bots = BOTS
    chain_method(IrHttp, 'is_a_bot', classmethod(is_a_bot))
