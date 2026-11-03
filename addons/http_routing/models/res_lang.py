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
- El cuerpo es el de la fuente, ``return self._get_active_by('code')``: un
  ``LangDataDict`` de los idiomas activos indexado por código, con un
  ``LangData`` vacío —falso— para el código que no está.
"""

from addons.base.models.res_lang import ResLang
from orm.method_chain import chain_method


def _get_frontend(cls):
    """
    ≙ ``_get_frontend`` (``odoo19c: :10-14``) — ``{code: lang}`` de los
    activos.

    :return: los idiomas disponibles para la petición en curso, indexados por
        código.
    """
    return cls._get_active_by('code')


def apply_res_lang_extensions():
    """Cuelga ``_get_frontend`` sobre ``base.ResLang`` — ≙ ``_inherit``."""
    chain_method(ResLang, '_get_frontend', classmethod(_get_frontend))
