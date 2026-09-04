"""``ir.ui.view`` extendido por ``web`` — metadata de tipo de vista.

Adaptación de ``odoo19c: addons/web/models/ir_ui_view.py``
(``odoo-tools@622ddc2a``, 32 líneas, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). Extiende ``ir.ui.view`` (ya portado en
``base/models/ir_ui_view.py``) con la metadata de icono/nombre visible por
tipo de vista que consume el selector de tipo del cliente web.

Medición símbolo-por-símbolo: **2** métodos de **1** clase (``IrUiView``).
El nodo ``class IrUiView`` no es un símbolo ausente — artefacto del medidor
(H-API-379): se extiende con funciones de módulo instaladas como
``classmethod`` (``chain_method`` con el descriptor explícito), no redeclarando la
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
from addons.base.models.ir_ui_view import (
    VIEW_TYPE_CHOICES,
    VIEW_TYPE_TEMPLATE,
    IrUiView,
)
from orm.method_chain import chain_method


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
    docstring del módulo) — excluye el tipo de plantilla igual que la
    referencia excluye ``qweb``: no es un tipo seleccionable por el usuario.
    Sobre por qué aquí ese valor se llama ``template``, ver
    ``ir_ui_view.VIEW_TYPE_TEMPLATE``.
    """
    view_info = _get_view_info(cls)
    return {
        type_: {
            'display_name': display_name,
            'icon': view_info[type_]['icon'],
            'multi_record': view_info[type_].get('multi_record', True),
        }
        for type_, display_name in VIEW_TYPE_CHOICES
        if type_ != VIEW_TYPE_TEMPLATE and type_ in view_info
    }


def apply_web_extensions():
    """Cuelga las dos extensiones de ``web`` sobre ``base.IrUiView``.

    Se invoca desde ``WebConfig.ready()`` (``web/apps.py::_EXTENSIONES``),
    mismo patrón que ``ir_http.py``/``res_partner.py``/``ir_model.py``.

    Se pasa ``classmethod(...)`` explícito: no hay implementación previa en
    ``base``, así que es el llamador quien declara el descriptor. El rodeo
    local ``_install_classmethod`` que vivía aquí se retiró al arreglar
    ``chain_method`` para descriptores (:ref:`h-api-381`, tarea #222).
    """
    chain_method(IrUiView, 'get_view_info', classmethod(get_view_info))
    chain_method(IrUiView, '_get_view_info', classmethod(_get_view_info))
