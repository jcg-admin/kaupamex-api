"""``res.lang`` extendido por ``http_routing`` — los idiomas del frontend.

Adaptación de ``odoo19c: addons/http_routing/models/res_lang.py`` (14 líneas,
LGPL-3). **1 símbolo en la fuente, 1 portado, 0 ausentes.**

Divergencias declaradas:

- ``_inherit = 'res.lang'`` → ``chain_method`` sobre ``base.ResLang``, no
  subclase. ``ResLang`` es un modelo **concreto** de Django: subclasearlo
  crearía herencia multi-tabla y por tanto una tabla y una migración nuevas
  para un addon que no añade ni un campo. Colgar el método sobre la clase es
  el idioma del árbol para extender un concreto
  (``addons/web/models/res_partner.py::apply_web_extensions``).
- El cuerpo de la fuente es ``return self._get_active_by('code')``, y
  ``_get_active_by`` es de ``base`` — medido:
  ``grep -n "_get_active_by" src/addons/base/models/res_lang.py`` da **0**.
  ``base`` es archivo de otro pase (sucesor #270 sobre ese mismo archivo), así
  que aquí se escribe **lo que ``_get_active_by('code')`` hace**: los idiomas
  activos indexados por su código. El día que ``base`` declare el helper, este
  cuerpo se reduce a la llamada.
- La fuente devuelve ``LangDataDict`` (su caché de datos de idioma); aquí un
  ``dict`` de filas ``ResLang``. Lo que los consumidores de este addon leen de
  cada valor —``.code`` y ``.url_code``— existe igual en la fila.
"""
from addons.base.models.res_lang import ResLang
from orm.method_chain import chain_method


def _get_frontend(cls):
    """≙ ``_get_frontend`` (``odoo19c: :10-14``) — ``{code: lang}`` de los activos.

    :return: los idiomas disponibles para la petición en curso, indexados por
        código.
    """
    return {lang.code: lang for lang in cls.objects.filter(active=True)}


def apply_res_lang_extensions():
    """Cuelga ``_get_frontend`` sobre ``base.ResLang`` — ≙ ``_inherit``."""
    chain_method(ResLang, '_get_frontend', classmethod(_get_frontend))
