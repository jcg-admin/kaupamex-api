"""``ir.http`` extendido por ``website`` — el consentimiento de cookies por sitio.

Adaptación de Odoo ``website/models/ir_http.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3). Porte quirúrgico: de los **29 símbolos** del archivo
fuente (27 métodos de ``IrHttp`` + 2 de ``ModelConverter``, medidos por AST)
se porta **1** — ``_is_allowed_cookie``
(``odoo19c: addons/website/models/ir_http.py:421-442``), que es el que el
bloque B5 de ``website.py`` (#538) consume.

Los otros 28 NO se omiten en silencio: pertenecen todos a la familia
enrutado/despacho/servido del frontend multi-sitio (``routing_map``,
``_match``, ``_serve_page``, ``_serve_redirect``, el reescritor de idioma, el
``ModelConverter`` de Werkzeug…), la misma familia que
``src/addons/base/models/ir_http.py`` declara **no portada** en su docstring:
en este árbol el enrutado y el despacho son la URLconf de Django más el
router de DRF. Su re-evaluación viaja con el sucesor ya registrado **#545**
(la enumeración sobre ``routing_map`` que bloqueó B2 de ``website.py``).

``_slug`` y ``_slug_matching`` — medidos en #261, siguen ausentes
=================================================================

El addon ``http_routing`` ya existe en este árbol (tarea #261) y con él
``ir.http._slug``, la composición ``<nombre>-<id>``. Eso reabre dos de los 28
símbolos que este archivo declara ausentes, porque los dos viven aquí y no
allá — **corrección de premisa medida**::

    grep -rln "_slug_matching" --include=*.py "$ODOO19C/addons" "$ODOO19C/odoo"
    -> addons/website/models/ir_http.py        (1 archivo, no http_routing)

Los dos siguen **ausentes**, ahora con su bloqueo medido y no por pertenecer
a la familia del enrutado:

- ``_slug`` (``odoo19c: addons/website/models/ir_http.py:64-70``) prefiere
  ``value.seo_name`` sobre el ``display_name`` cuando el registro lo declara.
  Bloqueo: ``grep -rn "seo_name" --include=*.py addons/ src/`` da **0**. El
  campo lo declara el mixin ``website.seo.metadata``
  (``odoo19c: addons/website/models/mixins.py:29``), que este árbol no porta
  — ``ir_ui_view.py:752-756`` ya lleva la marca de bloqueo y sucesor. Portar
  el override hoy sería un ``try/except AttributeError`` que nunca deja de
  levantar: un nombre sin mecanismo. Se porta con el mixin, en ese sucesor.

- ``_slug_matching`` (``:73-78``) marca los argumentos de tipo registro con
  ``slug_matching=True`` y reconstruye la URL con ``adapter.build``. Dos
  bloqueos: este ORM no tiene contexto por registro —``http_routing`` ya
  declara su análogo, el atributo ``_converter_value`` de ``ModelConverter``—
  y su único consumidor en la fuente es el propio archivo
  (**1** archivo en los 629 addons medidos), o sea que no habría quién lo
  llamara. Se porta con ``routing_map``, sucesor **#545**.

Divergencias declaradas:

- ``_inherit = 'ir.http'`` → **subclase de** ``addons.base.models.IrHttp``.
  Aquél es un modelo abstracto de Django, y heredarlo es la forma nativa del
  ``_inherit`` sobre abstracto — el precedente es
  ``addons/utm/models/ir_http.py``.
- ``request.env['website']`` → ``model_by_name('website')``: el despacho por
  nombre de este árbol (``orm.registry``), mismo canal que ya usa
  ``utm_mixin``. Evita además un import circular: ``website.py`` importa este
  módulo para llamar ``_is_allowed_cookie``.
- **Formato del consentimiento.** La fuente lee la cookie
  ``website_cookies_bar`` (JSON ``{'optional': bool}``). Aquí el
  consentimiento es **por categoría**: la cookie ``cookie_consent`` (JSON
  URL-encoded ``{'choices': {categoria: bool}}``, leída por ``_read_consent``
  de ``core.middleware.cookie_governance``). El ``'optional'`` de la fuente
  agrupa todo lo no requerido, así que «optional concedido» se traduce a
  «hay elecciones y TODAS las categorías están concedidas».
- **Rama legacy pre-16.0.** La fuente, ante una cookie que no es dict (el
  formato viejo ``"true"``), la borra vía ``future_response`` y devuelve
  ``False``. Aquí un JSON inválido o no-dict hace que ``_read_consent``
  devuelva ``{}`` → ``False``; la cookie **no** se borra desde aquí — emitir
  y suprimir cookies es responsabilidad de ``CookieGovernanceMiddleware``,
  no de este modelo.
- ``get_current_website()`` devuelve ``None`` donde la fuente devuelve un
  recordset vacío; ``None`` se lee igual que la fuente lee el recordset
  vacío (``cookies_bar`` falsy → sin barra → ``True``).
"""
from addons.base.models.ir_http import IrHttp as BaseIrHttp, get_current_request
from core.middleware.cookie_governance import _read_consent
from orm.registry import model_by_name


class IrHttp(BaseIrHttp):
    """``ir.http`` con el consentimiento por sitio (``odoo19c: ir_http.py:421-442``)."""

    _inherit = 'ir.http'

    class Meta:
        abstract = True

    @classmethod
    def _is_allowed_cookie(cls, cookie_type):
        """≙ ``_is_allowed_cookie`` (``odoo19c: :421-442``).

        Restringe el permiso de ``base``: una cookie ``'optional'`` sólo pasa
        si el sitio actual no gobierna cookies (sin barra) o si el titular
        concedió el consentimiento. Ver el docstring del módulo para las
        divergencias de formato y de la rama legacy.
        """
        result = super()._is_allowed_cookie(cookie_type)
        if result and cookie_type == 'optional':
            website = model_by_name('website').get_current_website()
            if website is None or not website.cookies_bar:
                # La barra de cookies está deshabilitada en este sitio: el
                # operador implementó (o decidió no tener) su propio
                # mecanismo de consentimiento.
                return True
            choices = _read_consent(get_current_request())
            # «optional concedido» ⇔ hay elecciones y todas las categorías
            # están concedidas (ver la divergencia de formato en el módulo).
            return bool(choices) and all(choices.values())

        # Passthrough: ya prohibida por otra razón, o un tipo de cookie que
        # este módulo no restringe.
        return result
