"""``wizard.ir.model.menu.create`` — dar entrada de menú a un modelo.

Adaptación de ``odoo19c: odoo/addons/base/wizard/wizard_ir_model_menu_create.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia preservados,
DEC-KX-03).

El asistente hace dos cosas en una: crea la acción de ventana que lista un
modelo, y cuelga del menú padre un ítem que la abre. Aquí es un
``classmethod`` — "formulario, no tabla", el precedente de este directorio.

Divergencia declarada — el ítem apunta a una RUTA, no a una acción
===================================================================

La referencia enlaza el menú con la acción por un campo ``Reference``::

    'action': 'ir.actions.act_window,%d' % action_id

``ir.ui.menu`` de este árbol **no declara** ``action``: declara ``route``, y su
docstring justifica por qué (``ir_ui_menu.py:33-35``) — el consumidor es el
router de un SPA, y *"un campo con el nombre de ``action`` mentiría"* sobre lo
que guarda.

Por eso ``menu_create`` conserva **ambas** mitades del trabajo de la fuente: la
acción de ventana se crea igual —es el registro que dice qué modelo se lista y
en qué vistas—, y el ítem de menú se cuelga con la ruta del SPA que la abre. La
correspondencia acción ↔ ruta la fija el llamador, que es quien conoce el
router; sin él, inventarla aquí sería fabricar una convención.
"""
from addons.base.models.ir_actions import IrActionsActWindow
from addons.base.models.ir_ui_menu import IrUiMenu

#: Modos de vista con que la fuente crea la acción (``odoo19c: :15``).
DEFAULT_VIEW_MODE = 'list,form'


class ModelMenuCreate:
    """≙ ``wizard.ir.model.menu.create`` (``odoo19c: :4-7``)."""

    @classmethod
    def menu_create(cls, name, menu, model, route, view_mode=DEFAULT_VIEW_MODE):
        """≙ ``menu_create`` (``odoo19c: :13-27``).

        :param name: etiqueta del ítem y de la acción — allá, el campo ``name``
            del asistente.
        :param menu: el ítem padre — allá, ``menu_id``.
        :param model: el ``ir.model`` cuyo listado abre el ítem. La fuente lo
            saca del contexto (``self.env.context.get('model_id')``); aquí es
            un parámetro, porque no hay contexto implícito que leer.
        :param route: la ruta del SPA que abre la acción. **Obligatoria**: es
            el enlace que allá pone el campo ``action``, y un ítem sin ella no
            abre nada. La columna además es NOT NULL, así que dejarla
            implícita crearía en silencio una **sección** —un nodo contenedor,
            ``ir_ui_menu.py:358``— en vez del ítem que el asistente promete.
        :returns: la pareja ``(acción, ítem de menú)`` creada.
        """
        accion = IrActionsActWindow.objects.create(
            name=name,
            type='ir.actions.act_window',
            res_model=model.model,
            view_mode=view_mode,
        )
        item = IrUiMenu.objects.create(
            name=name,
            parent=menu,
            route=route,
            # ``key`` es el xmlid de este árbol: único y obligatorio
            # (``ir_ui_menu.py:309-312``). La referencia no le pone xmlid a un
            # ítem creado en caliente — allá es opcional. Aquí la identidad
            # estable del ítem es su ruta, que ya es única por construcción:
            # dos ítems que abran lo mismo son el mismo ítem.
            key=route,
        )
        return accion, item
