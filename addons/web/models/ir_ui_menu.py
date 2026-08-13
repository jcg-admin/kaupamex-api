"""``ir.ui.menu`` extendido por ``web`` — shape de menú del cliente OWL.

Adaptación de ``odoo19c: addons/web/models/ir_ui_menu.py``
(``odoo-tools@622ddc2a``, 88 líneas, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). Un método (``load_web_menus``), que transforma el
dict plano de ``load_menus`` al shape que consumía el cliente OWL de la
referencia (``appID``/``xmlid``/``actionID``/``webIconData``...).

Medición símbolo-por-símbolo: **1** método de **1** clase (``IrUiMenu``). El
nodo ``class IrUiMenu`` no es un símbolo ausente — artefacto del medidor
(H-API-379): se extiende con una función de módulo + ``chain_method``, no
redeclarando la clase.

**No es el consumidor actual, y se declara por qué (medido hoy)**
====================================================================

``authz/controllers/main.py::MyMenuView`` (líneas 47-89) sirve
``model.objects.load_menus_tree(...)`` — el árbol **anidado** que el SPA
React ya consume, no el dict plano + shape OWL de ``load_web_menus``. Ese
mismo archivo lo documenta explícitamente (línea 51-54): *"Todo el
mecanismo... vive en el manager del modelo"*, y el docstring de
``load_menus`` en ``base/models/ir_ui_menu.py:200-204`` fija la decisión:
*"El endpoint me/menu/ no sirve hoy esta forma... migrarlo es un cambio del
contrato público, que se decide aparte... no se hace de rebote al adaptar
el modelo"*.

Eso no vuelve a ``load_web_menus`` un símbolo sin destino posible — se porta
igual, como método de conjunto propio del manager (``CapabilityPrunedMenuManager``,
mismo lugar que ``load_menus``/``load_menus_tree``), disponible para quien
lo necesite en ese shape. La razón para NO cablearlo en ``MyMenuView`` hoy es
que cambiar el contrato público del endpoint es una decisión de scope propia
del SPA (``kaupamex-ui``), no un efecto colateral de completar este archivo.

Adaptación de campos — divergencias ya fijadas en el docstring de
``base/models/ir_ui_menu.py`` (tabla de procedencia), aplicadas aquí:

===================================  ========================================
Referencia (``load_web_menus``)      Aquí
===================================  ========================================
``xmlid``                            ``key`` (misma tabla: "cumple el papel
                                      del xmlid de Odoo")
``actionID``/``actionModel``/
``actionPath`` (3 piezas, acción
polimórfica resuelta)                ``route`` (1 pieza: el destino ES la
                                      ruta SPA, no una ``ir.actions.*``
                                      referenciada — misma tabla, fila
                                      ``action``)
``webIcon`` (triple
``"iconClass,color,bg"`` armado
para apps)                           ``web_icon`` verbatim — el campo nunca
                                      guarda ese formato (misma tabla, fila
                                      ``web_icon_data``: "el SPA resuelve el
                                      icono por nombre"); no hay nada que
                                      separar
``webIconData``/
``webIconDataMimetype``/
``backgroundImage``                  siempre ``None`` — no existe icono
                                      binario ni imagen de fondo en este
                                      modelo (misma tabla, fila
                                      ``web_icon_data``: "no se porta")
===================================  ========================================

La resolución "si es app y no tiene acción propia, toma la del primer
descendiente que sí tenga" (``while child and not action_id: ...``) sí se
porta verbatim — es lógica de recorrido del árbol, no de formato de campo.
"""
from orm.method_chain import chain_method

from addons.base.models.ir_ui_menu import CapabilityPrunedMenuManager


def load_web_menus(self, user, capabilities, superadmin=False):
    """≙ ``load_web_menus`` (``odoo19c: web/models/ir_ui_menu.py:12-87``).

    Ver el docstring del módulo para las divergencias de campo (todas
    medidas contra la tabla de procedencia de ``base/models/ir_ui_menu.py``)
    y por qué no es el shape que sirve hoy ``MyMenuView``.
    """
    menus = self.load_menus(user, capabilities, superadmin)

    web_menus = {}
    for menu_id, menu in menus.items():
        if menu_id == 'root':
            web_menus['root'] = {
                'id': 'root',
                'name': menu['name'],
                'children': menu['children'],
                'appID': False,
                'xmlid': '',
                'route': False,
                'webIcon': None,
                'webIconData': None,
                'webIconDataMimetype': None,
                'backgroundImage': None,
            }
            continue

        route = menu['route']
        if menu_id == menu['app_id'] and not route:
            # ≙ "if it's an app take action of first (sub)child having one
            # defined" — camina el primer hijo hasta encontrar una ruta.
            child = menu
            while child and not route:
                children = child['children']
                child = menus[children[0]] if children else None
                route = child['route'] if child else False

        web_menus[menu_id] = {
            'id': menu_id,
            'name': menu['name'],
            'children': menu['children'],
            'appID': menu['app_id'],
            'xmlid': menu['key'],
            'route': route,
            'webIcon': menu['web_icon'],
            'webIconData': None,
            'webIconDataMimetype': None,
        }
    return web_menus


def apply_web_extensions():
    """Cuelga ``load_web_menus`` sobre ``CapabilityPrunedMenuManager``.

    Sobre el **manager**, no sobre ``IrUiMenu`` — mismo lugar que
    ``load_menus``/``load_menus_tree`` (``base/models/ir_ui_menu.py``): son
    métodos de conjunto, no de registro. Se invoca desde
    ``WebConfig.ready()`` (``web/apps.py::_EXTENSIONES``).
    """
    chain_method(CapabilityPrunedMenuManager, 'load_web_menus', load_web_menus)
