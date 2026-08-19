"""``stock.replenish.mixin`` — el proveedor elegido al reabastecer
(Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/stock_replenish_mixin.py``
(``odoo19c: addons/purchase_stock/models/stock_replenish_mixin.py``, 18 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade: cuando la ruta elegida para reabastecer **compra** (alguna de sus
reglas tiene ``action == 'buy'``), el formulario deja elegir el proveedor. Si
la ruta no compra, el selector no se muestra — eso es todo lo que aporta este
archivo de la fuente.

Porte símbolo por símbolo — 4 de 4
====================================

*Métrica:* entradas del cuerpo de ``class StockReplenishMixin`` contadas por
AST sobre la fuente. Son **5** con ``_inherit``; **4** sin él: 2 campos y 2
métodos.
*Ciega a:* lo que otros addons cuelgan sobre el mismo mixin (dropship,
subcontratación) — ninguno portado.

=================================================  ==============================
Símbolo de la referencia (línea)                   Dónde queda en este puerto
=================================================  ==============================
``supplier_id`` (``:9``)                           ``SUPPLIER_FIELD`` (fábrica)
``show_vendor`` (``:10``)                          ``property`` ``show_vendor``
``_compute_show_vendor`` (``:12-15``)              método homónimo
``_get_show_vendor`` (``:17-18``)                  método homónimo, verbatim
=================================================  ==============================

Divergencias declaradas — las dos son herencia del sitio, no decisiones nuevas
==============================================================================

**D-1 — ``supplier_id`` se porta como FÁBRICA, no como campo colgado.**
``stock.StockReplenishMixin`` en este árbol es una **clase Python plana**, no
un modelo abstracto de Django (D-1 de ``addons/stock/models/
stock_replenish_mixin.py``): no tiene tabla donde colgar una columna. El árbol
ya fijó la forma para el otro campo del mismo mixin —``ROUTE_FIELD()``, una
fábrica que cada consumidor concreto declara en su propia clase— y este puerto
la repite en vez de inventar una segunda. ``SUPPLIER_FIELD()`` produce el
mismo ``Many2one('product.ProductSupplierinfo')`` que la fuente declara.

**D-2 — ``show_vendor`` es ``property``, no campo calculado.** La fuente lo
declara ``compute='_compute_show_vendor'`` **sin** ``store=``, así que tampoco
tiene columna allá; el motor de ``@api.depends`` que lo invalidaría no está
construido en este árbol (tarea #191). Misma forma que ``allowed_route_ids``
del mixin base, y la que ``H-API-611`` fija para este caso: el método de
cálculo conserva su nombre verbatim y la ``property`` lo invoca.

Nota de forma sobre ``_compute_show_vendor``
==============================================

La fuente itera el *recordset* (``for rec in self``) y **escribe** el campo;
aquí una instancia **es** un registro, así que el método **devuelve** el valor
y la ``property`` lo expone. Es la misma traducción que el mixin base ya hizo
con ``_compute_allowed_route_ids``.
"""
import models
from addons.stock.models.stock_replenish_mixin import StockReplenishMixin

import fields


#: ≙ ``supplier_id`` (``odoo19c: :9``) — «Vendor».
#:
#: Fábrica, no campo colgado (D-1 del docstring): el mixin no tiene tabla, así
#: que cada consumidor concreto declara ``supplier = SUPPLIER_FIELD()`` en su
#: propia clase. Espeja a ``ROUTE_FIELD`` del mixin base.
def SUPPLIER_FIELD(**kwargs):
    kwargs.setdefault('null', True)
    kwargs.setdefault('blank', True)
    kwargs.setdefault('on_delete', models.SET_NULL)
    kwargs.setdefault('verbose_name', 'Proveedor')
    kwargs.setdefault(
        'help_text',
        'Proveedor con el que se reabastece cuando la ruta compra '
        '(Odoo supplier_id).')
    return fields.Many2one('product.ProductSupplierinfo', **kwargs)


def show_vendor(self):
    """≙ ``show_vendor`` (``odoo19c: :10``) — D-2 del docstring."""
    return self._compute_show_vendor()


def _compute_show_vendor(self):
    """≙ ``_compute_show_vendor`` (``odoo19c: :12-15``).

    La fuente lee ``rec.route_id``; aquí el campo que ``ROUTE_FIELD()``
    declara en cada consumidor concreto se llama ``route`` (convención de
    nombres del árbol: el ``_id`` de la fuente se cae). Se lee con
    ``getattr(..., None)`` porque el mixin no garantiza que el consumidor lo
    haya declarado — sin ruta no hay proveedor que mostrar.
    """
    route = getattr(self, 'route', None)
    if route is None:
        return False
    return self._get_show_vendor(route)


def _get_show_vendor(self, route):
    """≙ ``_get_show_vendor`` (``odoo19c: :17-18``) — verbatim.

    La fuente: ``any(r.action == 'buy' for r in route.rule_ids)``. Aquí
    ``StockRule.ACTION_BUY`` no existe todavía — lo declara este mismo addon
    en ``stock_rule.py`` como ``ACTION_BUY = 'buy'``; se compara contra el
    literal para no crear una dependencia de import circular entre dos módulos
    del mismo addon.
    """
    return any(rule.action == 'buy' for rule in route.rule_ids.all())


def apply_purchase_stock_stock_replenish_mixin_extensions():
    """Cuelga sobre ``stock.StockReplenishMixin`` lo que ``purchase_stock`` le
    añade — ≙ ``_inherit``.

    ``setattr`` directo y no ``extend_model``: el destino es una **clase Python
    plana**, no un modelo registrado en ``apps``, así que
    ``lazy_model_operation`` nunca la resolvería. El guard ``hasattr`` es el
    mismo criterio idempotente de ``add_field_if_absent``: ``ready()`` puede
    correr más de una vez en el mismo proceso (autoreloader).
    """
    if not hasattr(StockReplenishMixin, 'show_vendor'):
        StockReplenishMixin.show_vendor = property(show_vendor)
    if not hasattr(StockReplenishMixin, '_compute_show_vendor'):
        StockReplenishMixin._compute_show_vendor = _compute_show_vendor
    if not hasattr(StockReplenishMixin, '_get_show_vendor'):
        StockReplenishMixin._get_show_vendor = _get_show_vendor
