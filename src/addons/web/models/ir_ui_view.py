"""``ir.ui.view`` extendido por ``web`` — metadata de tipo de vista.

Adaptación de ``odoo19c: addons/web/models/ir_ui_view.py``
(``odoo-tools@622ddc2a``, 32 líneas, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). Extiende ``ir.ui.view`` (ya portado en
``base/models/ir_ui_view.py``) con la metadata de icono/nombre visible por
tipo de vista que consume el selector de tipo del cliente web.

Medición símbolo-por-símbolo: **2** métodos de **1** clase (``IrUiView``).
El nodo ``class IrUiView`` no es un símbolo ausente — artefacto del medidor
(H-API-379): se extiende con funciones de módulo instaladas como
``classmethod`` (``_install_classmethod``, abajo), no redeclarando la
clase. **2 de 2 portados**, **0 ausentes**.

Adaptación de vocabulario
==========================

``self.fields_get(['type'], ['selection'])['type']['selection']`` de la
referencia lee las opciones del campo Selection ``type`` a través del
introspector de campos de Odoo. Aquí ``VIEW_TYPE_CHOICES``
(``base/models/ir_ui_view.py:121-130``) ya es exactamente ese par
``(valor, nombre_visible)`` — es el ``choices=`` real del campo Django
``type``, verbatim de la fuente (ocho tipos) — así que se reusa
directamente en vez de reconstruir un introspector genérico que este árbol
no tiene y que aquí no hace falta: el consumidor sólo necesita ESTE campo.

``get_view_info``/``_get_view_info`` no dependen de ningún registro
concreto en la referencia (se invocan sobre un recordset vacío,
``self.env['ir.ui.view'].get_view_info()``) — es introspección a nivel de
modelo. Se instalan aquí como ``classmethod``, igual que
``ir_model.py::apply_web_extensions`` hace con sus cuatro extensiones.
"""
from addons.base.models.ir_ui_view import VIEW_TYPE_CHOICES, IrUiView


def _get_view_info(cls):
    """≙ ``_get_view_info`` (``odoo19c: web/models/ir_ui_view.py:22-31``).

    Verbatim de la referencia: nombre de icono (y ``multi_record`` cuando
    difiere del default) por tipo de vista consultable desde el cliente.
    """
    return {
        'list': {'icon': 'oi oi-view-list'},
        'form': {'icon': 'fa fa-address-card', 'multi_record': False},
        'graph': {'icon': 'fa fa-area-chart'},
        'pivot': {'icon': 'oi oi-view-pivot'},
        'kanban': {'icon': 'oi oi-view-kanban'},
        'calendar': {'icon': 'fa fa-calendar'},
        'search': {'icon': 'oi oi-search'},
    }


def get_view_info(cls):
    """≙ ``get_view_info`` (``odoo19c: web/models/ir_ui_view.py:9-20``).

    Combina el icono de ``_get_view_info`` con el nombre visible de
    ``VIEW_TYPE_CHOICES`` (el ``choices=`` real del campo ``type``, ver el
    docstring del módulo) — excluye ``qweb`` igual que la referencia, que no
    es un tipo seleccionable por el usuario.
    """
    view_info = _get_view_info(cls)
    return {
        type_: {
            'display_name': display_name,
            'icon': view_info[type_]['icon'],
            'multi_record': view_info[type_].get('multi_record', True),
        }
        for type_, display_name in VIEW_TYPE_CHOICES
        if type_ != 'qweb' and type_ in view_info
    }


def _install_classmethod(cls, name, func):
    """Instala ``func`` como ``classmethod`` de ``cls``, idempotente.

    NO se usa ``chain_method`` (``orm/method_chain.py``): su chequeo de
    idempotencia no reconoce descriptores ``classmethod`` (ver el docstring
    homónimo en ``ir_model.py`` de este mismo addon, donde se verificó el
    fallo). Guard local: si ``cls.__dict__[name]`` ya envuelve exactamente
    ``func``, no-op.
    """
    existing = cls.__dict__.get(name)
    if isinstance(existing, classmethod) and existing.__func__ is func:
        return
    setattr(cls, name, classmethod(func))


def apply_web_extensions():
    """Cuelga las dos extensiones de ``web`` sobre ``base.IrUiView``.

    Se invoca desde ``WebConfig.ready()`` (``web/apps.py::_EXTENSIONES``),
    mismo patrón que ``ir_http.py``/``res_partner.py``/``ir_model.py``.
    """
    _install_classmethod(IrUiView, 'get_view_info', get_view_info)
    _install_classmethod(IrUiView, '_get_view_info', _get_view_info)
