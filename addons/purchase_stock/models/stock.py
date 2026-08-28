"""``stock.picking`` / ``stock.warehouse`` / ``stock.warehouse.orderpoint`` /
``stock.lot`` — el almacén que se reabastece comprando (Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/stock.py``
(``odoo19c: addons/purchase_stock/models/stock.py``, 354 líneas, LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade, en una frase por modelo:

- **El albarán** sabe de qué orden de compra vino y cuánto tardó en llegar.
- **El almacén** gana la ruta «Comprar» y su regla: marcar ``buy_to_resupply``
  es lo que hace que una necesidad de este almacén termine en una solicitud de
  cotización.
- **El punto de pedido** gana proveedor: cuando su ruta compra, el
  reabastecimiento automático necesita saber a quién.
- **El lote** sabe con qué compras entró.

Porte símbolo por símbolo — 21 de 45
=====================================

*Métrica:* entradas del cuerpo de las cinco clases contadas por AST sobre la
fuente. Con ``_inherit`` son 50; sin él **45**: 14 campos y 31 métodos.
*Ciega a:* si un símbolo portado se comporta igual en ejecución; y a lo que
otros addons cuelgan sobre los mismos cinco modelos.

``stock.picking`` — 6 de 7
----------------------------

.. list-table::
   :header-rows: 1
   :widths: 34 14 52

   * - Símbolo (línea)
     - Estado
     - Nota
   * - ``purchase_id`` (``:13-15``)
     - portado
     - ``property`` ``purchase`` — es ``related=``, no columna
   * - ``days_to_arrive`` (``:17``)
     - portado
     - ``property``
   * - ``delay_pass`` (``:18``)
     - portado
     - ``property``
   * - ``_compute_effective_date`` (``:20-26``)
     - portado
     - verbatim
   * - ``_compute_date_order`` (``:28-30``)
     - portado
     - verbatim
   * - ``_search_days_to_arrive`` (``:32-34``)
     - portado
     - devuelve el dominio, igual que la fuente
   * - ``_search_delay_pass`` (``:36-38``)
     - portado
     - ídem
   * - ``_action_done`` (``:40-42``)
     - **bloqueado**
     - ``grep -rn "def action_acknowledge" addons/ src/`` → 0

``stock.warehouse`` — 8 de 10
-------------------------------

Los ocho métodos se portan; los dos campos también. Nada bloqueado aquí — es
el bloque más completo del archivo, porque ``stock.StockWarehouse`` de este
árbol ya trae los nueve ganchos que la fuente encadena
(``_find_or_create_global_route``, ``_get_receive_rules_dict``,
``_get_receive_routes_values``, ``_format_rulename``, ``get_rules_dict``,
``_get_routes_values``, ``_get_all_routes``, ``_create_or_update_route``,
``_generate_global_route_rules_values``).

Salvedad: el XML ID ``purchase_stock.route_warehouse0_buy`` **no está
sembrado** —este puerto no siembra datos XML—, así que
``_find_or_create_global_route`` cae a su rama de búsqueda por nombre y, si
tampoco encuentra, crea la ruta «Comprar». Es exactamente la conducta que la
fuente tiene en una base sin ese dato, no una divergencia.

``stock.return.picking`` — 0 de 2
-----------------------------------

**Bloqueado entero, medido:** ``grep -rn "stock.return.picking" addons/ src/``
→ **0**. El modelo no existe en este árbol; ``addons/stock/models/
return_request.py`` declara ``ReturnRequest``/``ReturnItem``, que es un
mecanismo distinto (una solicitud de devolución del cliente, con estado y
evidencias), no el asistente de devolución de un albarán. Colgar
``_prepare_move_default_values`` sobre ``ReturnRequest`` sería inventar una
relación que la referencia no declara.

``stock.warehouse.orderpoint`` — 6 de 21
------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 38 14 48

   * - Símbolo (línea)
     - Estado
     - Nota
   * - ``supplier_id`` (``:145-149``)
     - portado
     - FK ``supplier``
   * - ``show_supplier`` (``:144``)
     - portado
     - ``property``
   * - ``supplier_id_placeholder`` (``:150``)
     - portado
     - ``property``
   * - ``vendor_ids`` (``:151``)
     - portado
     - ``property`` (``related=`` sin columna)
   * - ``effective_vendor_id`` (``:152-155``)
     - portado
     - ``property``; su ``search=`` queda bloqueado
   * - ``_compute_show_supplier`` (``:192-198``)
     - portado
     - lo consume la ``property``
   * - ``_inverse_supplier_id`` (``:200-203``)
     - portado
     - verbatim
   * - ``_compute_supplier_id_placeholder`` (``:205-209``)
     - portado
     - verbatim
   * - ``_compute_effective_vendor_id`` (``:211-214``)
     - portado
     - verbatim
   * - ``_inverse_route_id`` (``:158-162``)
     - portado
     - ``chain_method``
   * - ``_get_default_route`` (``:252-259``)
     - portado
     - ``chain_method``
   * - ``_get_default_supplier`` (``:261-268``)
     - portado
     - usa ``StockRule._get_matching_supplier`` de este addon
   * - ``_get_lead_days_values`` (``:270-274``)
     - portado
     - ``combine`` de diccionarios
   * - ``_prepare_procurement_values`` (``:299-302``)
     - portado
     - ídem
   * - ``_get_replenishment_order_notification`` (``:276-297``)
     - portado
     - devuelve el descriptor; sin la URL de Odoo
   * - ``_compute_deadline_date`` (``:164-167``)
     - **nada que portar**
     - su cuerpo es ``super()``; sólo añade ``@api.depends``
   * - ``_compute_qty_to_order_computed`` (``:169-174``)
     - **nada que portar**
     - ídem
   * - ``_compute_lead_days`` (``:176-178``)
     - **nada que portar**
     - ídem
   * - ``_compute_days_to_order`` (``:180-190``)
     - **bloqueado por mecanismo**
     - ``days_to_order`` es ``property`` aquí, sin ``_compute_`` que encadenar
   * - ``_compute_show_supply_warning`` (``:230-235``)
     - **bloqueado por mecanismo**
     - ídem con ``show_supply_warning``
   * - ``available_vendor`` (``:156``)
     - **bloqueado**
     - campo sólo-búsqueda sobre no almacenado
   * - ``_search_effective_vendor_id`` (``:216-221``)
     - **bloqueado**
     - ídem
   * - ``_search_available_vendor`` (``:223-228``)
     - **bloqueado**
     - ídem; además ``_prepare_sellers`` → 0 hits
   * - ``action_view_purchase`` (``:237-250``)
     - **bloqueado**
     - ``_for_xml_id`` → 0 definiciones
   * - ``_get_replenishment_multiple_alternative`` (``:304-320``)
     - **bloqueado**
     - ``_select_seller`` → 0 hits
   * - ``_quantity_in_progress`` (``:322-329``)
     - **bloqueado**
     - depende de ``product._get_quantity_in_progress``, bloqueado en ``product.py``

``stock.lot`` — 3 de 4
------------------------

``purchase_order_ids``, ``purchase_order_count`` y ``_compute_purchase_order_ids``
se portan como ``property`` + método. ``action_view_po`` queda **bloqueado**
por lo mismo que ``action_view_purchase``: ``_for_xml_id`` no existe (0
definiciones en el árbol; el único hit de ``grep -rn "_for_xml_id"`` es una
mención en el docstring de ``addons/stock/models/res_partner.py:56`` que
declara esta misma ausencia).

Divergencias declaradas
========================

**D-1 — los tres ``compute`` degenerados no se portan.** ``_compute_deadline_date``,
``_compute_qty_to_order_computed`` y ``_compute_lead_days`` tienen por cuerpo
entero ``return super()...``: existen sólo para **añadir un ``@api.depends``**
al motor de invalidación. Ese motor no está construido en este árbol (tarea
#191), así que portarlos produciría tres envoltorios que devuelven lo que
envuelven. Se declaran y no se portan — que es distinto de omitirlos.

**D-2 — ``buy_to_resupply`` es ``property`` con *setter*, no columna.** La
fuente lo declara ``compute=`` + ``inverse=`` + ``default=True``: un valor que
**se deriva** de si el almacén está en la ruta de compra y que **se escribe**
metiéndolo o sacándolo de esa ruta. No hay columna que persistir — el dato vive
en la relación ``route.warehouse_ids``. Aquí es exactamente eso: ``property``
que lee y *setter* que escribe la relación, con los nombres de la fuente en los
dos métodos (``_compute_buy_to_resupply`` / ``_inverse_buy_to_resupply``).

**D-3 — sin ``relativedelta``.** Sólo la necesitaba
``_get_replenishment_multiple_alternative``, que queda bloqueado por otra
razón. No hay nada que sustituir aquí.

**D-4 — los descriptores de acción no llevan URL de Odoo.** El
``_get_replenishment_order_notification`` de la fuente arma un enlace
``/odoo/action-purchase.action_rfq_form/{id}``. Este stack no tiene esa ruta;
el descriptor conserva la estructura y el ``label``, y deja la ``url`` con la
ruta del recurso (``/purchase/order/{id}``) — misma información, el
enrutamiento lo decide el cliente. Mismo criterio que
``addons/stock/models/res_partner.py`` ya fijó para ``action_view_stock_serial``.
"""
from collections import defaultdict

from django.apps import apps
from django.utils import timezone

import fields
import models
from orm.environments import get_context
from orm.method_chain import chain_method
from orm.model_classes import extend_model

#: ≙ ``'buy'`` — el ``stock.rule.action`` que este addon añade. Literal por la
#: misma razón que en ``product.py``: evita un ciclo de imports entre módulos
#: hermanos del addon.
ACTION_BUY = 'buy'

#: ≙ ``'purchase_stock.route_warehouse0_buy'`` — el XML ID de la ruta global de
#: compra que ``_find_or_create_global_route`` busca (``odoo19c: :71, :87``).
BUY_ROUTE_XMLID = 'purchase_stock.route_warehouse0_buy'

#: El nombre con el que la ruta se crea cuando el XML ID no está sembrado
#: (≙ ``_('Buy')`` de la fuente).
BUY_ROUTE_NAME = 'Comprar'


def _merge_vals(new, previous):
    """``combine`` para los hooks que devuelven un diccionario — ≙ el patrón
    ``res = super(); res.update(propio); return res`` de la fuente."""
    combined = dict(previous or {})
    combined.update(new or {})
    return combined


def _union_qs(new, previous):
    """``combine`` para los hooks que devuelven un *queryset* y acumulan —
    ≙ el ``routes |= ...`` de la fuente."""
    if new is None:
        return previous
    if previous is None:
        return new
    ids = set(new.values_list('pk', flat=True))
    ids |= set(previous.values_list('pk', flat=True))
    return new.model.objects.filter(pk__in=ids)


def _buy_rules():
    """Las reglas con acción «comprar» — el filtro que cinco métodos repiten."""
    return apps.get_model('stock', 'StockRule').objects.filter(action=ACTION_BUY)


# =========================================================================
# stock.picking
# =========================================================================

def picking_purchase(self):
    """≙ ``purchase_id`` (``odoo19c: :13-15``).

    Es ``related='move_ids.purchase_line_id.order_id'``: no una columna, sino
    la proyección de la orden de compra sobre los movimientos del albarán. La
    fuente toma el primero (un ``related`` sobre un to-many se queda con uno);
    aquí se hace explícito con ``.first()``.
    """
    move = self.move_ids.exclude(purchase_line__isnull=True).first()
    return move.purchase_line.order_id if move is not None else None


def _compute_effective_date(self):
    """≙ ``_compute_effective_date`` (``odoo19c: :20-26``).

    La fecha real de llegada: sólo cuenta si el albarán está hecho, el destino
    **no** es un proveedor (una devolución no es una llegada) y hay fecha de
    validación.
    """
    if (self.state == self.STATE_DONE
            and self.location_dest is not None
            and self.location_dest.usage != 'supplier'
            and self.date_done):
        return self.date_done
    return None


def days_to_arrive(self):
    """≙ ``days_to_arrive`` (``odoo19c: :17``) — ``compute`` sin ``store``."""
    return self._compute_effective_date()


def _compute_date_order(self):
    """≙ ``_compute_date_order`` (``odoo19c: :28-30``).

    La fecha desde la que se cuenta el retraso: la de la orden de compra si la
    hay, y si no el momento actual (que da retraso cero).
    """
    purchase = self.purchase
    return purchase.date_order if purchase is not None else timezone.now()


def delay_pass(self):
    """≙ ``delay_pass`` (``odoo19c: :18``) — ``compute`` sin ``store``.

    La fuente lo declara ``index=True``, que sobre un campo sin ``store`` no
    crea índice: no hay columna que indexar. Se conserva la observación y no el
    argumento.
    """
    return self._compute_date_order()


def _search_days_to_arrive(cls, operator, value):
    """≙ ``_search_days_to_arrive`` (``odoo19c: :32-34``) — verbatim.

    Devuelve el dominio con el que buscar por este campo sin columna: se
    traduce a una condición sobre ``date_done``, que sí la tiene.
    """
    return [('date_done', operator, value)]


def _search_delay_pass(cls, operator, value):
    """≙ ``_search_delay_pass`` (``odoo19c: :36-38``) — verbatim.

    ``purchase_id.date_order`` de la fuente es aquí
    ``move_ids.purchase_line.order_id.date_order``: el camino completo, porque
    ``purchase`` es una ``property`` y no una relación navegable.
    """
    return [('move_ids.purchase_line.order_id.date_order', operator, value)]


# =========================================================================
# stock.warehouse
# =========================================================================

def _compute_buy_to_resupply(self):
    """≙ ``_compute_buy_to_resupply`` (``odoo19c: :54-57``).

    ¿Este almacén se reabastece comprando? Sí cuando está entre los almacenes
    de la ruta de su regla de compra.
    """
    if self.buy_pull is None or self.buy_pull.route is None:
        return False
    return self.buy_pull.route.warehouse_ids.filter(pk=self.pk).exists()


def _inverse_buy_to_resupply(self, value):
    """≙ ``_inverse_buy_to_resupply`` (``odoo19c: :59-68``).

    Escribir el campo es meter o sacar el almacén de la ruta de compra. Si la
    regla del almacén todavía no existe, la fuente busca cualquier regla de
    compra de ese almacén para llegar a su ruta; se conserva.
    """
    buy_route = self.buy_pull.route if self.buy_pull is not None else None
    if buy_route is None:
        rule_rec = _buy_rules().filter(warehouse=self).first()
        buy_route = rule_rec.route if rule_rec is not None else None
    if buy_route is None:
        return
    if value:
        buy_route.warehouse_ids.add(self)
    else:
        buy_route.warehouse_ids.remove(self)


def buy_to_resupply(self):
    """≙ ``buy_to_resupply`` (``odoo19c: :48-51``) — D-2 del docstring."""
    return self._compute_buy_to_resupply()


def _find_buy_route(self):
    """La ruta global «Comprar», creándola si hace falta.

    Extraído porque tres métodos de la fuente repiten la misma llamada a
    ``_find_or_create_global_route`` con los mismos dos argumentos
    (``odoo19c: :71, :87``).
    """
    return self._find_or_create_global_route(BUY_ROUTE_XMLID, BUY_ROUTE_NAME)


def _create_or_update_route(self):
    """≙ ``_create_or_update_route`` (``odoo19c: :70-75``).

    Antes de crear las rutas del almacén, se asegura de que el almacén esté en
    la ruta global de compra cuando ``buy_to_resupply`` lo pide.

    Devuelve ``None`` para que ``chain_method`` ejecute a continuación el
    método previo — que es el ``super()`` de la fuente, y el que devuelve el
    valor real.
    """
    purchase_route = self._find_buy_route()
    if purchase_route is not None and self.buy_to_resupply:
        purchase_route.warehouse_ids.add(self)
    return None


def _generate_global_route_rules_values(self):
    """≙ ``_generate_global_route_rules_values`` (``odoo19c: :77-98``).

    Declara la **regla de compra** del almacén: qué crear la primera vez y qué
    actualizar después. ``propagate_cancel`` sigue la misma condición de la
    fuente —sólo con recepción en más de un paso—, y el ``depends`` declara los
    dos campos cuyo cambio obliga a regenerarla.

    ``combine=_merge_vals``: la fuente parte del diccionario del ``super()`` y
    le añade esta entrada.
    """
    route_rec = self._find_buy_route()
    location = self.lot_stock
    return {
        'buy_pull': {
            'depends': ['reception_steps', 'buy_to_resupply'],
            'create_values': {
                'action': ACTION_BUY,
                'picking_type': self.in_type,
                'company': self.company,
                'route': route_rec,
                'propagate_cancel': self.reception_steps != 'one_step',
            },
            'update_values': {
                'active': self.buy_to_resupply,
                'name': self._format_rulename(location, False, 'Buy'),
                'location_dest': location,
                'propagate_cancel': self.reception_steps != 'one_step',
            },
        },
    }


def _get_all_routes(self):
    """≙ ``_get_all_routes`` (``odoo19c: :100-103``).

    Suma la ruta de la regla de compra a las que el ``super()`` ya devolvía —
    sólo si el almacén se reabastece comprando y la regla existe.
    """
    if not self.buy_to_resupply or self.buy_pull is None or not self.buy_pull.route_id:
        return None
    route_model = apps.get_model('stock', 'StockRoute')
    return route_model.objects.filter(pk=self.buy_pull.route_id)


def get_rules_dict(self):
    """≙ ``get_rules_dict`` (``odoo19c: :105-109``).

    Añade a la cadena de saltos del almacén la de recepción, que es la que la
    regla de compra alimenta.

    ``combine`` propio (``_merge_rules_dict``): el diccionario está indexado
    por almacén, así que la fusión tiene que entrar un nivel más — un
    ``update`` plano reemplazaría la entrada entera del almacén.
    """
    return {self.pk: self._get_receive_rules_dict()}


def _merge_rules_dict(new, previous):
    """``combine`` de ``get_rules_dict`` — fusiona por almacén, no por raíz."""
    combined = {k: dict(v) for k, v in (previous or {}).items()}
    for warehouse_id, rules_rec in (new or {}).items():
        combined.setdefault(warehouse_id, {}).update(rules_rec)
    return combined


def _get_routes_values(self):
    """≙ ``_get_routes_values`` (``odoo19c: :111-114``).

    Añade la ruta de recepción al contrato de rutas del almacén, con
    ``buy_to_resupply`` como campo del que depende.
    """
    return self._get_receive_routes_values('buy_to_resupply')


def _update_name_and_code(cls, warehouses, new_name=False, new_code=False):
    """≙ ``_update_name_and_code`` (``odoo19c: :116-122``).

    Al renombrar el almacén, la regla de compra lleva su nombre dentro: hay que
    reescribirlo. La fuente reemplaza **la primera** ocurrencia; se conserva.

    Es ``@classmethod`` aquí porque el método previo lo es
    (``addons/stock/models/stock_warehouse.py:1552``) y ``chain_method``
    preserva el descriptor: si se instalara como método de instancia, la
    llamada ``cls._update_name_and_code(...)`` reventaría en ejecución
    (``H-API-738``).
    """
    if not new_name:
        return None
    for warehouse in warehouses:
        rule_rec = warehouse.buy_pull
        if rule_rec is not None and rule_rec.name:
            rule_rec.name = rule_rec.name.replace(warehouse.name, new_name, 1)
            rule_rec.save(update_fields=['name', 'updated_at'])
    return None


# =========================================================================
# stock.warehouse.orderpoint
# =========================================================================

def _compute_show_supplier(self):
    """≙ ``_compute_show_supplier`` (``odoo19c: :192-198``).

    La columna de proveedor sólo tiene sentido cuando la ruta efectiva del
    punto de pedido es una ruta de compra.
    """
    route_rec = self.effective_route
    if route_rec is None:
        return False
    return _buy_rules().filter(route=route_rec).exists()


def show_supplier(self):
    """≙ ``show_supplier`` (``odoo19c: :144``) — ``compute`` sin ``store``."""
    return self._compute_show_supplier()


def _inverse_supplier_id(self):
    """≙ ``_inverse_supplier_id`` (``odoo19c: :200-203``).

    Elegir proveedor sin haber elegido ruta fija la ruta de compra: la fuente
    toma la primera regla con acción «comprar» y usa su ruta.
    """
    if self.route is None and self.supplier is not None:
        rule_rec = _buy_rules().first()
        if rule_rec is not None:
            self.route = rule_rec.route


def _get_default_supplier(self):
    """≙ ``_get_default_supplier`` (``odoo19c: :261-268``).

    El proveedor que el sistema elegiría si el usuario no eligió ninguno. Lo
    resuelve ``StockRule._get_matching_supplier``, que este mismo addon porta
    en ``stock_rule.py``; se busca por ``apps.get_model`` para no crear un
    ciclo de imports entre módulos hermanos.

    La fuente devuelve un recordset vacío cuando no aplica; aquí ``None``.
    """
    if not self.show_supplier or self.product_id is None:
        return None
    StockRule = apps.get_model('stock', 'StockRule')
    return StockRule._get_matching_supplier(
        self.product, self.qty_to_order, self.product_uom, self.company, {})


def _compute_supplier_id_placeholder(self):
    """≙ ``_compute_supplier_id_placeholder`` (``odoo19c: :205-209``).

    El texto gris del selector: el nombre del proveedor que se usaría si no se
    elige ninguno.
    """
    default_supplier = self._get_default_supplier()
    return default_supplier.display_name if default_supplier is not None else ''


def supplier_id_placeholder(self):
    """≙ ``supplier_id_placeholder`` (``odoo19c: :150``)."""
    return self._compute_supplier_id_placeholder()


def _compute_effective_vendor_id(self):
    """≙ ``_compute_effective_vendor_id`` (``odoo19c: :211-214``).

    El contacto que va a recibir la compra: el del proveedor elegido, o el del
    que se elegiría por defecto.
    """
    supplier = self.supplier if self.supplier_id else self._get_default_supplier()
    return supplier.partner if supplier is not None else None


def effective_vendor_id(self):
    """≙ ``effective_vendor_id`` (``odoo19c: :152-155``) — ``store=False``.

    Su ``search='_search_effective_vendor_id'`` queda **bloqueado**: buscar
    sobre un campo sin columna exige el mecanismo de ``search=`` de la
    referencia, que este ORM no tiene (medido: ``grep -rn "search=" src/orm/
    fields*.py`` → 0 kwargs de ese nombre).
    """
    return self._compute_effective_vendor_id()


def vendor_ids(self):
    """≙ ``vendor_ids`` (``odoo19c: :151``) — ``related='product_id.seller_ids'``.

    Sin columna: es la proyección de las tarifas de proveedor del producto.
    """
    if self.product_id is None:
        return apps.get_model('product', 'ProductSupplierinfo').objects.none()
    return self.product.product_tmpl.seller_ids.all()


def _inverse_route_id(self):
    """≙ ``_inverse_route_id`` (``odoo19c: :158-162``).

    Quitar la ruta quita el proveedor: sin ruta de compra no hay a quién
    comprar. Devuelve ``None`` para que la cadena siga al método previo, que es
    el ``super()`` de la fuente.
    """
    if self.route is None:
        self.supplier = None
    return None


def _get_default_route(self):
    """≙ ``_get_default_route`` (``odoo19c: :252-259``).

    Si el producto tiene proveedores y alguna de las reglas del punto de pedido
    lleva a una ruta de compra, ésa es la ruta por defecto. Si no, cede al
    método previo devolviendo ``None``.
    """
    if self.product_id is None:
        return None
    if not self.product.product_tmpl.seller_ids.exists():
        return None
    buy_route_ids = set(_buy_rules().values_list('route', flat=True))
    for rule_rec in self.rule_ids:
        if rule_rec.route_id in buy_route_ids:
            return rule_rec.route
    return None


def _get_lead_days_values(self):
    """≙ ``_get_lead_days_values`` (``odoo19c: :270-274``).

    Añade la tarifa de proveedor elegida a los valores con los que se calcula
    el plazo — es de ahí de donde sale el ``delay`` del proveedor.
    """
    if self.supplier_id is None:
        return None
    return {'supplierinfo': self.supplier}


def _prepare_procurement_values(self, date=False):
    """≙ ``_prepare_procurement_values`` (``odoo19c: :299-302``).

    Pasa el proveedor elegido al abastecimiento, para que la regla de compra no
    tenga que volver a decidirlo.
    """
    return {'supplierinfo_id': self.supplier}


def _get_replenishment_order_notification(self):
    """≙ ``_get_replenishment_order_notification`` (``odoo19c: :276-297``).

    El aviso «se generó esta orden de reabastecimiento» con el enlace a la
    orden. D-4: el descriptor conserva su forma y su ``label``; la URL apunta
    al recurso de este stack, no a la ruta del cliente web de Odoo.
    """
    POL = apps.get_model('purchase', 'PurchaseOrderLine')
    queryset = POL.objects.filter(orderpoint=self)
    written_after = get_context().get('written_after')
    if written_after:
        queryset = queryset.filter(updated_at__gte=written_after)
    line = queryset.first()
    if line is None:
        return None
    order = line.order_id
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': 'Se generó la siguiente orden de reabastecimiento',
            'message': '%s',
            'links': [{
                'label': str(order),
                'url': f'/purchase/order/{order.pk}',
            }],
            'sticky': False,
            'next': {'type': 'ir.actions.act_window_close'},
        },
    }


# =========================================================================
# stock.lot
# =========================================================================

def _compute_purchase_order_ids(self):
    """≙ ``_compute_purchase_order_ids`` (``odoo19c: :338-347``).

    Las compras con las que este lote entró: se recorren sus líneas de
    movimiento hechas, se filtran las que vinieron de un proveedor o del
    tránsito, y se recoge la orden de la línea de compra.

    La fuente agrupa por lote (opera sobre un recordset); aquí una instancia es
    un lote, así que el ``defaultdict`` se reduce a un conjunto. Se conserva
    igualmente para que la forma del método sea legible contra la fuente.
    """
    StockMoveLine = apps.get_model('stock', 'StockMoveLine')
    PurchaseOrder = apps.get_model('purchase', 'PurchaseOrder')
    purchase_orders = defaultdict(set)
    for move_line in StockMoveLine.objects.filter(lot=self, state='done'):
        move = move_line.move
        if move is None or not move.purchase_line_id:
            continue
        picking = move.picking
        if picking is None or picking.location is None:
            continue
        if picking.location.usage not in ('supplier', 'transit'):
            continue
        purchase_orders[move_line.lot_id].add(move.purchase_line.order_id)
    return PurchaseOrder.objects.filter(pk__in=purchase_orders[self.pk])


def purchase_order_ids(self):
    """≙ ``purchase_order_ids`` (``odoo19c: :335``) — ``store=False``."""
    return self._compute_purchase_order_ids()


def purchase_order_count(self):
    """≙ ``purchase_order_count`` (``odoo19c: :336``)."""
    return self._compute_purchase_order_ids().count()


# =========================================================================
# instalación
# =========================================================================

def _install_picking(model):
    """Los dos ``search`` del albarán son ``@api.model`` en la fuente."""
    chain_method(model, '_search_days_to_arrive',
                 classmethod(_search_days_to_arrive))
    chain_method(model, '_search_delay_pass', classmethod(_search_delay_pass))


def _install_warehouse(model):
    """Los seis ganchos del almacén; tres necesitan ``combine`` propio.

    ``buy_to_resupply`` se instala aquí y no en ``propiedades=``: necesita
    ``fset``, y ese bloque de ``extend_model`` sólo sabe montar propiedades de
    sólo lectura. Es el ``inverse=`` de la fuente (D-2 del docstring), y sin él
    escribir el campo reventaría con ``AttributeError``.
    """
    if not hasattr(model, 'buy_to_resupply'):
        model.buy_to_resupply = property(
            buy_to_resupply, _inverse_buy_to_resupply)
    chain_method(model, '_create_or_update_route', _create_or_update_route)
    chain_method(model, '_generate_global_route_rules_values',
                 _generate_global_route_rules_values, combine=_merge_vals)
    chain_method(model, '_get_all_routes', _get_all_routes, combine=_union_qs)
    chain_method(model, 'get_rules_dict', get_rules_dict,
                 combine=_merge_rules_dict)
    chain_method(model, '_get_routes_values', _get_routes_values,
                 combine=_merge_vals)
    # ``@classmethod`` porque el previo lo es — ver el docstring del método.
    chain_method(model, '_update_name_and_code',
                 classmethod(_update_name_and_code))


def _install_orderpoint(model):
    """Los cinco ganchos del punto de pedido; dos acumulan diccionarios."""
    chain_method(model, '_inverse_route_id', _inverse_route_id)
    chain_method(model, '_get_default_route', _get_default_route)
    chain_method(model, '_get_lead_days_values', _get_lead_days_values,
                 combine=_merge_vals)
    chain_method(model, '_prepare_procurement_values',
                 _prepare_procurement_values, combine=_merge_vals)
    chain_method(model, '_get_replenishment_order_notification',
                 _get_replenishment_order_notification)


def apply_purchase_stock_stock_extensions():
    """Cuelga sobre los cuatro modelos de ``stock`` lo que ``purchase_stock``
    les añade — ≙ los cinco ``_inherit`` de la fuente (uno de ellos,
    ``stock.return.picking``, sin destino en este árbol)."""
    extend_model(
        'stock', 'StockPicking',
        propiedades={
            'purchase': picking_purchase,
            'days_to_arrive': days_to_arrive,
            'delay_pass': delay_pass,
        },
        metodos={
            '_compute_effective_date': _compute_effective_date,
            '_compute_date_order': _compute_date_order,
        },
        luego=_install_picking,
    )

    extend_model(
        'stock', 'StockWarehouse',
        campos={
            'buy_pull': fields.Many2one(
                'stock.StockRule', null=True, blank=True,
                on_delete=models.SET_NULL, related_name='buy_warehouse_ids',
                verbose_name='Regla de compra',
                help_text='Regla que convierte una necesidad de este almacén '
                          'en una solicitud de cotización (Odoo buy_pull_id).',
            ),
        },
        metodos={
            '_compute_buy_to_resupply': _compute_buy_to_resupply,
            '_inverse_buy_to_resupply': _inverse_buy_to_resupply,
            '_find_buy_route': _find_buy_route,
        },
        luego=_install_warehouse,
    )

    extend_model(
        'stock', 'StockWarehouseOrderpoint',
        campos={
            'supplier': fields.Many2one(
                'product.ProductSupplierinfo', null=True, blank=True,
                on_delete=models.SET_NULL, related_name='orderpoint_ids',
                verbose_name='Tarifa de proveedor',
                help_text='Tarifa del proveedor con el que se reabastece '
                          '(Odoo supplier_id).',
            ),
        },
        propiedades={
            'show_supplier': show_supplier,
            'supplier_id_placeholder': supplier_id_placeholder,
            'effective_vendor_id': effective_vendor_id,
            'vendor_ids': vendor_ids,
        },
        metodos={
            '_compute_show_supplier': _compute_show_supplier,
            '_inverse_supplier_id': _inverse_supplier_id,
            '_compute_supplier_id_placeholder': _compute_supplier_id_placeholder,
            '_compute_effective_vendor_id': _compute_effective_vendor_id,
            '_get_default_supplier': _get_default_supplier,
        },
        luego=_install_orderpoint,
    )

    extend_model(
        'stock', 'StockLot',
        propiedades={
            'purchase_order_ids': purchase_order_ids,
            'purchase_order_count': purchase_order_count,
        },
        metodos={'_compute_purchase_order_ids': _compute_purchase_order_ids},
    )
