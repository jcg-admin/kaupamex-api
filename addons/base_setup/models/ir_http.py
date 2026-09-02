"""``ir.http`` extendido por ``base_setup`` — el efecto visual en la sesión.

Adaptación de ``odoo19c: addons/base_setup/models/ir_http.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia preservados,
DEC-KX-03; mecanismo: **copia + adaptación**).

Los 2 símbolos de la fuente están portados: la clase y su ``session_info``.

Divergencias declaradas
=======================

- ``_inherit = 'ir.http'`` → **subclase de** ``addons.base.models.IrHttp``,
  que es un modelo abstracto de Django. Es la forma nativa del ``_inherit``
  sobre un abstracto y el precedente del árbol es
  ``addons/utm/models/ir_http.py``, que lo declara con las mismas palabras.
- **La firma cambia, y no es cosmética.** La fuente escribe
  ``result = super().session_info()`` porque allá el productor del cuerpo de
  sesión **es** un método de ``ir.http``. Aquí el productor es
  ``web.controllers.session.build_session_info``, una función de módulo, y el
  árbol ya tiene su punto de extensión declarado —
  ``register_session_info_extension``, con la firma de ida y vuelta
  ``(user, cuerpo) -> cuerpo`` que hace las veces del ``super()``. Es la misma
  divergencia que ``addons/authz_timeout/models/ir_http.py`` numera como su
  cuarta, y se resuelve igual: el método recibe el cuerpo en vez de pedirlo.
- **El registro lo hace ``ready()``**, no este módulo: ``web`` no conoce a sus
  extensores, igual que ``ir.http`` no conoce quién lo hereda.
"""
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_http import IrHttp as BaseIrHttp

from .res_config_settings import SHOW_EFFECT_PARAM


class IrHttp(BaseIrHttp):
    """≙ ``IrHttp`` (``odoo19c: base_setup/models/ir_http.py:6-13``)."""

    _inherit = 'ir.http'

    class Meta:
        abstract = True

    @classmethod
    def session_info(cls, user, session_info_dict):
        """≙ ``session_info`` (``odoo19c: :9-13``).

        Añade ``show_effect`` al cuerpo de sesión **sólo para usuario
        interno** — la guarda ``self.env.user._is_internal()`` de la fuente,
        verbatim: un usuario de portal no configura la plataforma y no tiene
        por qué enterarse de su ajuste.

        ``bool(get_param(...))`` es el de la fuente y su semántica coincide
        aquí: ``SystemParameter.set_param`` **borra** la clave cuando el valor
        es falso (``ir_config_parameter.py:181-186``), así que un ajuste
        apagado devuelve ``None`` y no la cadena ``'False'``.
        """
        if user is not None and getattr(user, 'is_authenticated', False) \
                and user._is_internal():
            session_info_dict['show_effect'] = bool(
                SystemParameter.get_param(SHOW_EFFECT_PARAM))
        return session_info_dict
