"""``stock.rule`` / ``stock.route`` — la regla que compra (Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/stock_rule.py``
(``odoo19c: addons/purchase_stock/models/stock_rule.py``, 411 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade: una **cuarta acción** a la regla de inventario. Hasta ahora una
regla podía arrastrar (``pull``), empujar (``push``) o ambas; con este addon
puede **comprar**. Cuando una necesidad llega a una regla ``buy``, el resultado
no es un movimiento de inventario sino una solicitud de cotización al
proveedor.

Alrededor de esa acción viven tres cosas: cómo se elige al proveedor, cuánto
plazo añade su tiempo de entrega, y cómo se agrupan varias necesidades en una
sola orden.

Porte símbolo por símbolo — 12 de 20
=====================================

*Métrica:* entradas del cuerpo de ``class StockRule`` y ``class StockRoute``
contadas por AST sobre la fuente. Con ``_inherit`` son 22; sin él **20**: 1
campo (``action``, que es un ``selection_add``) y 19 métodos.
*Ciega a:* si un símbolo portado se comporta igual en ejecución.

.. list-table::
   :header-rows: 1
   :widths: 42 14 44

   * - Símbolo (línea)
     - Estado
     - Nota
   * - ``action`` — ``selection_add`` (``:18-20``)
     - portado
     - añade ``('buy', 'Buy')`` a ``ACTION_CHOICES``
   * - ``_get_message_dict`` (``:22-31``)
     - portado
     - ``combine`` de diccionarios
   * - ``_compute_picking_type_code_domain`` (``:33-38``)
     - portado
     - ``combine=extend_list``
   * - ``_onchange_action`` (``:40-43``)
     - portado
     - método normal — no hay evento de formulario
   * - ``run`` (``:45-56``)
     - portado
     - muta ``values`` y cede al ``super()``
   * - ``_filter_warehouse_routes`` (``:167-172``)
     - portado
     - ``@classmethod``, como el previo
   * - ``_get_matching_supplier`` (``:174-201``)
     - portado
     - con D-2 (la rama de tarifa por cantidad)
   * - ``_notify_responsible`` (``:208-209``)
     - portado
     - punto de extensión vacío, verbatim
   * - ``_get_lead_days`` (``:211-239``)
     - portado
     - con D-2; ``combine`` propio
   * - ``_get_procurements_to_merge_groupby`` (``:241-250``)
     - portado
     - verbatim
   * - ``_get_procurements_to_merge`` (``:252-260``)
     - portado
     - verbatim
   * - ``_merge_procurements`` (``:262-296``)
     - portado
     - verbatim
   * - ``_push_prepare_move_copy_values`` (``:394-399``)
     - portado
     - ``combine`` de diccionarios
   * - ``_get_partner_id`` (``:401-402``)
     - portado
     - verbatim
   * - ``StockRoute._is_valid_resupply_route_for_product`` (``:408-411``)
     - portado
     - ``chain_method``
   * - ``_run_buy`` (``:58-165``)
     - **bloqueado**
     - 7 campos de la orden de compra ausentes — abajo
   * - ``_prepare_purchase_order`` (``:326-356``)
     - **bloqueado**
     - los mismos 7
   * - ``_make_po_get_domain`` (``:358-392``)
     - **bloqueado**
     - los mismos 7 + ``buyer_id`` del contacto
   * - ``_update_purchase_order_line`` (``:298-324``)
     - **bloqueado**
     - ``_select_seller`` + ``_fix_tax_included_price_company``
   * - ``_post_vendor_notification`` (``:203-206``)
     - **bloqueado**
     - ``markupsafe`` no es dependencia + ``message_post`` sobre estos modelos

El bloqueo grande: la orden de compra que ``_run_buy`` crearía
================================================================

Los cuatro métodos bloqueados de ese eje son **una sola ausencia vista cuatro
veces**: ``purchase.order`` de este árbol
(``addons/purchase/models/purchase_order.py``, 107 líneas) declara cinco
campos —``name``, ``partner``, ``date_order``, ``state``, ``note``— y
``_run_buy`` escribe **siete que no existen**:

.. code-block:: text

    user_id · company_id · currency_id · origin · payment_term_id ·
    fiscal_position_id · date_planned

De ellos, ``purchase_stock`` aporta en este mismo pase ``picking_type_id`` y
``dest_address_id`` (ver ``purchase_order.py``); los siete restantes son del
addon ``purchase``, que está **fuera del write-set** de este pase. Escribir
``_run_buy`` contra campos inexistentes produce un método que revienta en
ejecución y pasa todos los gates estáticos — exactamente el modo de fallo que
``H-API-738`` registra.

Además, ``_make_po_get_domain`` necesita ``partner.buyer_id``
(``grep -rn "buyer_id" addons/ src/ --include=*.py`` → 0) y
``_update_purchase_order_line`` necesita
``account.tax._fix_tax_included_price_company`` (→ 0).

Divergencias declaradas
========================

**D-1 — ``selection_add`` se expresa mutando ``choices``.** La fuente usa el
kwarg ``selection_add=[('buy', 'Buy')]`` con ``ondelete={'buy': 'cascade'}``.
Este ORM no tiene ese kwarg (``fields.Selection`` es ``models.CharField``,
``src/orm/fields_selection.py:9``), así que el valor se añade **a la lista de
opciones del campo ya declarado** — que es lo que ``selection_add`` produce
allá. El ``ondelete`` queda **bloqueado**: es la política de qué hacer con las
reglas ``buy`` si se desinstala el addon, y este árbol no tiene desinstalación
de addons (0 modelos de módulo con estado de instalación poblado).

**D-2 — ``_select_seller`` no existe; la selección cae al filtro base.**
Medido: ``grep -rn "def _select_seller" addons/ src/ --include=*.py`` → **0**.
Es el método que elige **qué tarifa** de proveedor aplica según cantidad,
fecha y unidad. Lo que sí existe es su primer paso:
``ProductSupplierinfo.filtered_suppliers``
(``addons/product/models/product_supplierinfo.py:302-322``), que filtra por
empresa, proveedor activo y variante — las tres condiciones que la fuente
aplica antes de ordenar por precio.

Consecuencia declarada, no escondida: ``_get_matching_supplier`` y
``_get_lead_days`` **eligen la primera tarifa válida por secuencia**, no la de
menor precio para la cantidad pedida. Las dos primeras ramas de
``_get_matching_supplier`` (proveedor forzado por el abastecimiento, y
proveedor del punto de pedido) se portan **sin degradación**: son las que el
reabastecimiento automático usa, y no pasan por ``_select_seller``.

**D-3 — ``markupsafe`` no es dependencia.** Medido (preámbulo de la tanda, y
``grep -i markupsafe uv.lock`` → vacío). ``_post_vendor_notification`` la usa
para componer HTML seguro; el sustituto del árbol es
``django.utils.html.format_html``. No se porta igualmente porque su otra mitad
—``records_to_notify.message_post(...)`` sobre el punto de pedido— tampoco
existe: el mecanismo de bitácora (*chatter*) no está construido sobre estos
modelos.

**D-4 — los tres métodos de fusión de necesidades usan ``groupby`` de
``itertools``.** La fuente importa ``odoo.tools.groupby``, que agrupa **sin
ordenar previamente** (recorre y acumula en un diccionario). El de
``itertools`` exige el orden. Aquí se agrupa con un diccionario explícito, que
es lo que el de la fuente hace por dentro y conserva el orden de aparición.
"""
from collections import defaultdict

from django.apps import apps

from addons.stock.models.stock_rule import Procurement
from orm.environments import get_context
from orm.method_chain import chain_method, extend_list
from orm.model_classes import extend_model

#: ≙ ``('buy', 'Buy')`` del ``selection_add`` (``odoo19c: :18-20``).
ACTION_BUY = 'buy'
ACTION_BUY_LABEL = 'Comprar'

#: ≙ los 365 días que la fuente suma cuando no hay proveedor
#: (``odoo19c: :221-222``). Constante nombrada porque aparece tres veces.
NO_VENDOR_FOUND_DELAY = 365


def _merge_vals(new, previous):
    """``combine`` para los hooks que devuelven un diccionario."""
    combined = dict(previous or {})
    combined.update(new or {})
    return combined


def _merge_lead_days(new, previous):
    """``combine`` de ``_get_lead_days`` — ≙ el patrón de la fuente.

    Los dos lados son ``(delays, delay_description)``. Los plazos se **suman**
    clave a clave (la fuente hace ``delays['total_delay'] += ...`` sobre el
    diccionario del ``super()``) y las descripciones se concatenan en orden:
    primero las del ``super()``, después las que añade este addon.
    """
    if new is None:
        return previous
    if previous is None:
        return new
    new_delays, new_desc = new
    delays, desc = previous
    accumulated = defaultdict(float, delays or {})
    for key, value in (new_delays or {}).items():
        accumulated[key] += value
    return accumulated, list(desc or []) + list(new_desc or [])


def _group_preserving_order(items, key):
    """≙ ``odoo.tools.groupby`` (D-4 del docstring).

    Agrupa sin exigir que la entrada venga ordenada, conservando el orden de
    aparición de cada grupo. Devuelve una lista de listas.
    """
    groups = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    return list(groups.values())


def _buy_rules():
    """Las reglas con acción «comprar»."""
    return apps.get_model('stock', 'StockRule').objects.filter(action=ACTION_BUY)


def _sellers_of(product):
    """Las tarifas de proveedor de un producto — ≙ ``product.seller_ids``.

    Vive aquí porque cuatro métodos la repiten y porque el camino no es
    obvio: las tarifas cuelgan de la **plantilla**, no de la variante
    (``addons/product/models/product_supplierinfo.py:194``).
    """
    if product is None or product.product_tmpl_id is None:
        return []
    return list(product.product_tmpl.seller_ids.all())


# --- stock.rule ------------------------------------------------------------

def _get_message_dict(self):
    """≙ ``_get_message_dict`` (``odoo19c: :22-31``).

    El texto que describe qué hace una regla de compra. Se añade a los que el
    ``super()`` ya devolvía para las otras tres acciones (``combine``).

    La nota final de la fuente se conserva porque es una advertencia real: la
    regla de compra **no basta sola**; funciona en combinación con las reglas
    de la ruta de recepción.
    """
    __, destination, __, __ = self._get_message_values()
    return {
        ACTION_BUY: (
            f'Cuando se necesiten productos en <b>{destination}</b>, <br/> '
            'se crea una solicitud de cotización para cubrir la necesidad.<br/>'
            'Nota: esta regla se usa en combinación con las reglas<br/>'
            'de la ruta o rutas de recepción'
        ),
    }


def _compute_picking_type_code_domain(self):
    """≙ ``_compute_picking_type_code_domain`` (``odoo19c: :33-38``).

    Una regla de compra sólo admite operaciones de entrada. Se acumula sobre lo
    que el ``super()`` devuelve (``combine=extend_list``), que en ``stock`` es
    la lista vacía.
    """
    return [] if self.action != ACTION_BUY else ['incoming']


def _onchange_action(self):
    """≙ ``_onchange_action`` (``odoo19c: :40-43``).

    Una regla de compra no tiene ubicación de origen: la mercancía viene de
    fuera. En la fuente es ``@api.onchange`` y lo dispara el formulario; aquí
    es un método normal, mismo criterio que ``_onchange_buy_route`` en
    ``product.py``.
    """
    if self.action == ACTION_BUY:
        self.location_src = None


def run(cls, procurements, raise_user_error=True):
    """≙ ``run`` (``odoo19c: :45-56``).

    Antes de despachar las necesidades, añade a las que van por una ruta de
    compra la **ruta de recepción del almacén de su empresa**: sin ella la
    mercancía comprada llegaría al almacén sin pasos de recepción.

    Muta ``procurement.values`` **en el sitio** y devuelve ``None``, así que
    ``chain_method`` ejecuta a continuación el método previo con los mismos
    objetos ya modificados — que es exactamente lo que el ``super()`` de la
    fuente recibe.

    ``@classmethod`` porque el previo lo es
    (``addons/stock/models/stock_rule.py:1055``); instalarlo de instancia haría
    que ``cls.run(...)`` reventara sólo al ejecutarse (``H-API-738``).
    """
    StockWarehouse = apps.get_model('stock', 'StockWarehouse')
    wh_by_comp = {}
    for procurement in procurements:
        routes = procurement.values.get('route_ids')
        if not routes:
            continue
        if not any(rule_rec.action == ACTION_BUY
                   for route in routes for rule_rec in route.rule_ids.all()):
            continue
        company = procurement.company_id
        if company not in wh_by_comp:
            wh_by_comp[company] = list(
                StockWarehouse.objects.filter(company=company))
        reception_routes = [wh.reception_route for wh in wh_by_comp[company]
                            if wh.reception_route_id]
        procurement.values['route_ids'] = list(routes) + [
            r for r in reception_routes if r not in routes]
    return None


def _filter_warehouse_routes(cls, product, warehouses, route):
    """≙ ``_filter_warehouse_routes`` (``odoo19c: :167-172``).

    Una ruta de compra sólo sirve para un producto que tenga proveedores. Si no
    los tiene, la ruta se descarta (``False``); si los tiene —o la ruta no
    compra— se cede al método previo devolviendo ``None``.

    ``@classmethod`` porque el previo lo es
    (``addons/stock/models/stock_rule.py:1175``).
    """
    if any(rule_rec.action == ACTION_BUY for rule_rec in route.rule_ids.all()):
        if not _sellers_of(product):
            return False
    return None


def _get_matching_supplier(cls, product_id, product_qty, product_uom,
                           company_id, values):
    """≙ ``_get_matching_supplier`` (``odoo19c: :174-201``).

    Quién va a surtir esta necesidad, en el orden de la fuente:

    1. el proveedor que el abastecimiento ya trae (``supplierinfo_id``);
    2. el del punto de pedido, si lo tiene;
    3. la tarifa que corresponda a la cantidad y la fecha — **D-2**: sin
       ``_select_seller`` se cae al filtro base y se toma la primera válida.

    Y el respaldo de la fuente, verbatim en intención: *«Fall back on a
    supplier for which no price may be defined. Not ideal, but better than
    blocking the user.»*

    ``@classmethod`` — divergencia declarada: la fuente lo llama sobre una
    regla (``rule._get_matching_supplier(...)``) pero sólo usa ``self`` para
    reenviarlo a ``_get_partner_id(values, self)``, que lo **ignora**
    (``odoo19c: :401-402``). Su único llamador vivo en este puerto es
    ``StockWarehouseOrderpoint._get_default_supplier`` (``stock.py``), que lo
    invoca sobre la clase; hacerlo ``@classmethod`` es lo que mantiene esa
    llamada coherente (``H-API-738``).
    """
    if values.get('supplierinfo_id'):
        return values['supplierinfo_id']

    orderpoint = values.get('orderpoint_id')
    if orderpoint is not None and getattr(orderpoint, 'supplier_id', None):
        return orderpoint.supplier

    ProductSupplierinfo = apps.get_model('product', 'ProductSupplierinfo')
    candidates = ProductSupplierinfo.filtered_suppliers(
        _sellers_of(product_id), company_id, product_id)
    if not candidates:
        return None

    # D-2: sin ``_select_seller`` no hay orden por precio para la cantidad;
    # se toma la primera por secuencia, que es el orden natural del modelo.
    matching_min_qty = [s for s in candidates
                    if product_qty is None or s.min_qty <= product_qty]
    return (matching_min_qty or candidates)[0]


def _notify_responsible(self, procurement):
    """≙ ``_notify_responsible`` (``odoo19c: :208-209``) — verbatim.

    Punto de extensión vacío. El comentario de la fuente es lo que lo
    justifica: *«Override in sale_purchase_stock and purchase_mrp to notify
    salesperson or MO responsible»*. Se porta con cuerpo vacío porque su valor
    es el contrato, no el cálculo — mismo criterio que
    ``StockMove._action_synch_order`` en ``stock``.
    """
    return None


def _get_lead_days(cls, rules, product, **values):
    """≙ ``_get_lead_days`` (``odoo19c: :211-239``).

    Suma al plazo acumulado el **tiempo de entrega del proveedor** y los
    **días para comprar** de la empresa. Las tres ramas de la fuente:

    - no hay regla de compra entre las reglas → no aporta nada;
    - hay regla pero no hay proveedor → suma 365 días y lo dice, que es la
      forma que la fuente tiene de hacer visible el hueco en vez de esconderlo;
    - hay proveedor → suma su ``delay`` más ``company.days_to_purchase``.

    D-2: cuando ``values`` no trae ``supplierinfo``, la fuente lo elige con
    ``_select_seller(quantity=None)``; aquí se toma la primera tarifa válida.

    ``@classmethod`` porque el previo lo es
    (``addons/stock/models/stock_rule.py:999``), con la misma firma
    ``(cls, rules, product, **values)``.
    """
    ctx = get_context()
    bypass_delay_description = ctx.get('bypass_delay_description')
    buy_rules = [r for r in rules if r.action == ACTION_BUY]
    if not buy_rules:
        return None

    delays = defaultdict(float)
    delay_description = []

    seller = values.get('supplierinfo')
    if seller is None:
        ProductSupplierinfo = apps.get_model('product', 'ProductSupplierinfo')
        company_rec = buy_rules[0].company
        candidates = ProductSupplierinfo.filtered_suppliers(
            _sellers_of(product), company_rec, product)
        seller = candidates[0] if candidates else None

    if seller is None:
        delays['total_delay'] += NO_VENDOR_FOUND_DELAY
        delays['no_vendor_found_delay'] += NO_VENDOR_FOUND_DELAY
        if not bypass_delay_description:
            delay_description.append(
                ('No se encontró proveedor',
                 f'+ {NO_VENDOR_FOUND_DELAY} día(s)'))
        return delays, delay_description

    buy_rule = buy_rules[0]
    if not ctx.get('ignore_vendor_lead_time'):
        supplier_delay = seller.delay or 0
        delays['total_delay'] += supplier_delay
        delays['purchase_delay'] += supplier_delay
        if not bypass_delay_description:
            delay_description.append(('Fecha de recepción', supplier_delay))
            delay_description.append(
                ('Plazo de entrega del proveedor', f'+ {supplier_delay} día(s)'))

    company_rec = buy_rule.company
    days_to_order = getattr(company_rec, 'days_to_purchase', 0) or 0 if company_rec else 0
    delays['total_delay'] += days_to_order
    if not bypass_delay_description:
        delay_description.append(('Fecha límite del pedido', days_to_order))
        delay_description.append(
            ('Días para comprar', f'+ {days_to_order} día(s)'))
    return delays, delay_description


def _get_procurements_to_merge_groupby(cls, procurement):
    """≙ ``_get_procurements_to_merge_groupby`` (``odoo19c: :241-250``).

    La clave por la que dos necesidades pueden compartir línea de compra. El
    comentario de la fuente es la parte que no hay que perder: **no** se
    agrupan necesidades de puntos de pedido distintos, por dos razones —
    ``_quantity_in_progress`` depende del punto de pedido de la línea, y el
    movimiento generado toma la ubicación del punto de pedido como destino.
    Con ``move_dest_ids`` esos dos puntos ya no aplican, y por eso la clave los
    excluye del agrupador.
    """
    orderpoint = procurement.values.get('orderpoint_id')
    move_dest = procurement.values.get('move_dest_ids')
    return (
        procurement.product_id,
        procurement.product_uom,
        procurement.values['propagate_cancel'],
        procurement.values.get('product_description_variants'),
        (orderpoint if (orderpoint and not move_dest) else None),
    )


def _get_procurements_to_merge(cls, procurements):
    """≙ ``_get_procurements_to_merge`` (``odoo19c: :252-260``).

    Agrupa las necesidades que usarían la misma línea de compra. D-4: el
    agrupador conserva el orden de aparición sin exigir entrada ordenada.
    """
    return _group_preserving_order(
        procurements, key=cls._get_procurements_to_merge_groupby)


def _merge_procurements(cls, procurements_to_merge):
    """≙ ``_merge_procurements`` (``odoo19c: :262-296``).

    Funde cada grupo en una sola necesidad: suma las cantidades y acumula los
    movimientos destino. El comentario de la fuente justifica por qué el resto
    de valores se toma de una necesidad **arbitraria** del grupo — ya se
    marcaron como equivalentes, así que sólo cambian la cantidad y dos claves.
    """
    merged_procurements = []
    for procurements in procurements_to_merge:
        quantity = 0
        move_dest_ids = []
        orderpoint_id = None
        procurement = None
        for procurement in procurements:
            destinations = procurement.values.get('move_dest_ids')
            if destinations:
                move_dest_ids.extend(
                    m for m in destinations if m not in move_dest_ids)
            if orderpoint_id is None and procurement.values.get('orderpoint_id'):
                orderpoint_id = procurement.values['orderpoint_id']
            quantity += procurement.product_qty
        if procurement is None:
            continue
        values = dict(procurement.values)
        values.update({
            'move_dest_ids': move_dest_ids,
            'orderpoint_id': orderpoint_id,
        })
        merged_procurements.append(Procurement(
            procurement.product_id, quantity, procurement.product_uom,
            procurement.location_id, procurement.name, procurement.origin,
            procurement.company_id, values,
        ))
    return merged_procurements


def _push_prepare_move_copy_values(self, move_to_copy, new_date):
    """≙ ``_push_prepare_move_copy_values`` (``odoo19c: :394-399``).

    El movimiento que continúa la cadena pierde su enlace con la línea de
    compra **salvo** cuando empuja hacia un proveedor: ahí es una devolución, y
    el enlace se recupera ascendiendo por la cadena
    (``_get_purchase_line_and_partner_from_chain``, portado en
    ``stock_move.py``).

    ``combine=_merge_vals``: la fuente parte del diccionario del ``super()``.
    """
    vals = {'purchase_line_id': None}
    if self.location_dest is not None and self.location_dest.usage == 'supplier':
        line, partner = move_to_copy._get_purchase_line_and_partner_from_chain()
        vals['purchase_line_id'] = line
        vals['partner_id'] = partner
    return vals


def _get_partner_id(cls, values, rule):
    """≙ ``_get_partner_id`` (``odoo19c: :401-402``) — verbatim.

    Devuelve el contacto con el que buscar tarifa. ``rule`` se recibe y **no se
    usa**: así es en la fuente, y se conserva porque es el parámetro que los
    addons que extienden este método sí consumen.
    """
    return values.get('supplierinfo_name') or (
        values.get('force_uom') and values.get('partner_id'))


# --- stock.route -----------------------------------------------------------

def _is_valid_resupply_route_for_product(self, product):
    """≙ ``StockRoute._is_valid_resupply_route_for_product`` (``odoo19c: :408-411``).

    Una ruta de compra sólo reabastece a un producto que tenga proveedores. Si
    la ruta no compra, se cede al método previo devolviendo ``None``.
    """
    if any(rule_rec.action == ACTION_BUY for rule_rec in self.rule_ids.all()):
        return bool(_sellers_of(product))
    return None


# --- instalación -----------------------------------------------------------

def _install_rule(model):
    """Añade la acción «comprar» y encadena los nueve ganchos de la regla."""
    # D-1: ``selection_add`` se expresa añadiendo la opción a las que el campo
    # ya declara. Se toca la lista de clase Y la del campo: la primera es la
    # que el código lee (``StockRule.ACTION_CHOICES``), la segunda la que la
    # validación de Django consulta.
    if not hasattr(model, 'ACTION_BUY'):
        model.ACTION_BUY = ACTION_BUY
    if all(value != ACTION_BUY for value, _label in model.ACTION_CHOICES):
        model.ACTION_CHOICES.append((ACTION_BUY, ACTION_BUY_LABEL))
    action_field = model._meta.get_field('action')
    if all(value != ACTION_BUY for value, _label in action_field.choices):
        action_field.choices = list(action_field.choices) + [(ACTION_BUY, ACTION_BUY_LABEL)]

    chain_method(model, '_get_message_dict', _get_message_dict,
                 combine=_merge_vals)
    chain_method(model, '_compute_picking_type_code_domain',
                 _compute_picking_type_code_domain, combine=extend_list)
    chain_method(model, '_onchange_action', _onchange_action)
    chain_method(model, 'run', classmethod(run))
    chain_method(model, '_filter_warehouse_routes',
                 classmethod(_filter_warehouse_routes))
    chain_method(model, '_get_matching_supplier',
                 classmethod(_get_matching_supplier))
    chain_method(model, '_notify_responsible', _notify_responsible)
    chain_method(model, '_get_lead_days', classmethod(_get_lead_days),
                 combine=_merge_lead_days)
    chain_method(model, '_get_procurements_to_merge_groupby',
                 classmethod(_get_procurements_to_merge_groupby))
    chain_method(model, '_get_procurements_to_merge',
                 classmethod(_get_procurements_to_merge))
    chain_method(model, '_merge_procurements', classmethod(_merge_procurements))
    chain_method(model, '_push_prepare_move_copy_values',
                 _push_prepare_move_copy_values, combine=_merge_vals)
    chain_method(model, '_get_partner_id', classmethod(_get_partner_id))


def _install_route(model):
    chain_method(model, '_is_valid_resupply_route_for_product',
                 _is_valid_resupply_route_for_product)


def apply_purchase_stock_stock_rule_extensions():
    """Cuelga sobre ``stock.StockRule`` y ``stock.StockRoute`` lo que
    ``purchase_stock`` les añade — ≙ los dos ``_inherit`` de la fuente."""
    extend_model('stock', 'StockRule', luego=_install_rule)
    extend_model('stock', 'StockRoute', luego=_install_route)
