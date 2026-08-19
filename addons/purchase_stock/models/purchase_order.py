"""``purchase.order`` — la orden de compra que genera su recepción
(Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/purchase_order.py``
(``odoo19c: addons/purchase_stock/models/purchase_order.py``, 468 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade: la orden de compra deja de terminar en sí misma. Gana un **tipo de
operación** (a qué almacén entra la mercancía), sabe **qué albaranes** nacieron
de ella, **cuándo llegó** lo primero y **cuánto** se ha recibido.

Porte símbolo por símbolo — 18 de 47
=====================================

*Métrica:* entradas del cuerpo de ``class PurchaseOrder`` contadas por AST
sobre la fuente. Son **48** con ``_inherit``; **47** sin él: 11 campos y 36
métodos (el AST cuenta 37 porque incluye ``_default_picking_type``, que la
fuente declara antes de los campos por ser su ``default=``).
*Ciega a:* si un símbolo portado se comporta igual en ejecución.

Lo portado
------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Forma aquí
   * - ``incoterm_location`` (``:20``)
     - campo ``Char``
   * - ``picking_type_id`` (``:23-24``)
     - campo ``picking_type`` (FK a ``stock.StockPickingType``)
   * - ``dest_address_id`` (``:22``)
     - campo ``dest_address`` (FK a ``base.ResPartner``)
   * - ``picking_ids`` (``:21``)
     - ``property`` — D-1
   * - ``incoming_picking_count`` (``:20``)
     - ``property``
   * - ``effective_date`` (``:31-32``)
     - ``property`` — D-1
   * - ``is_shipped`` (``:30``)
     - ``property``
   * - ``receipt_status`` (``:35-41``)
     - ``property``
   * - ``default_location_dest_id_usage`` (``:25-26``)
     - ``property`` (era ``related=``)
   * - ``_default_picking_type`` (``:16-17``)
     - ``@classmethod``
   * - ``_get_picking_type`` (``:342-349``)
     - ``@classmethod``, las tres búsquedas de la fuente
   * - ``_compute_picking_ids`` (``:43-46``)
     - método homónimo
   * - ``_compute_incoming_picking_count`` (``:48-51``)
     - ídem
   * - ``_compute_effective_date`` (``:53-57``)
     - ídem
   * - ``_compute_is_shipped`` (``:59-65``)
     - ídem
   * - ``_compute_receipt_status`` (``:67-77``)
     - ídem
   * - ``_compute_dest_address_id`` (``:79-81``)
     - ídem
   * - ``_get_destination_location`` (``:324-328``)
     - método homónimo
   * - ``_get_final_location_record`` (``:330-340``)
     - ídem
   * - ``_prepare_reference_vals`` (``:351-355``)
     - ídem
   * - ``_add_reference`` (``:436-439``)
     - ídem
   * - ``_remove_reference`` (``:441-444``)
     - ídem
   * - ``_is_display_stock_in_catalog`` (``:414-415``)
     - ídem

Lo NO portado, agrupado por su causa (no uno por uno, porque la causa es común)
--------------------------------------------------------------------------------

**Causa A — la orden de compra de este árbol tiene cinco campos.**
``addons/purchase/models/purchase_order.py`` (107 líneas) declara ``name``,
``partner``, ``date_order``, ``state`` y ``note``. Los siguientes métodos
escriben o leen campos que **no existen** y que pertenecen al addon
``purchase``, fuera del write-set de este pase:

.. code-block:: text

    company_id · currency_id · user_id · origin · date_planned ·
    invoice_ids · incoterm_id · order_line.product_uom_id

Caen aquí: ``_onchange_company_id`` (``:83-87``), ``_prepare_picking``
(``:357-372``), ``_create_picking`` (``:374-406``), ``retrieve_dashboard``
(``:239-260``), ``_prepare_invoice`` (``:286-289``), ``write`` (``:93-105``),
``_log_decrease_ordered_quantity`` (``:296-322``).

**Causa B — el método al que encadenan no existe.** Medido, cada uno con su
grep sobre ``addons/`` + ``src/``:

.. code-block:: text

    def button_approve                       → 0
    def retrieve_dashboard                   → 0
    def _prepare_grouped_data                → 0
    def action_add_from_catalog              → 0
    def _get_action_add_from_catalog_extra_context → 0
    def _get_domain_is_late                  → 0
    def _create_update_date_activity         → 0
    def _update_update_date_activity         → 0
    def _get_orders_to_remind                → 0
    def _get_product_catalog_order_line_info → 0
    def _get_product_price_and_data          → 0
    def _merge_po_post_process               → 0
    def _create_stock_moves                  → 0

Trece métodos que sólo existen para extender uno anterior. Instalarlos sería
el primer eslabón de una cadena sin eslabón base — ``H-API-733``.

**Causa C — ``_for_xml_id`` no existe** (0 definiciones en el árbol):
``action_view_picking`` (``:236-237``) y ``_get_action_view_picking``
(``:272-284``).

**Causa D — el mecanismo de bitácora (*chatter*) no cubre estos modelos.**
``message_post`` existe **sólo** en ``addons/mail/models/mail_thread.py:88``, y
ni ``purchase.order`` ni ``stock.picking`` heredan ese mixin en este árbol.
Caen: ``button_cancel`` (``:186-231``, cuyo cuerpo por lo demás sí sería
portable), ``_add_picking_info`` (``:408-419``) y los dos métodos de actividad
que lo llaman. ``_add_picking_info`` además usa ``markupsafe``, que no es
dependencia de este proyecto (medido en el preámbulo de la tanda).

**Causa E — depende de algo bloqueado en otro archivo de este addon.**
``on_time_rate`` (``:34``) es ``related='partner_id.on_time_rate'``, y ese
campo quedó bloqueado en ``res_partner.py`` de este addon (la orden apunta a un
usuario, no a un ``res.partner``). ``action_purchase_order_suggest``
(``:130-173``) depende de ``product.suggested_qty`` —portado— **y** de
``purchase.order.line._prepare_purchase_order_line``, que no existe (0 hits).

Divergencias declaradas
========================

**D-1 — los ``compute`` con ``store=True`` se portan como ``property``.**
``picking_ids`` y ``effective_date`` se declaran almacenados en la fuente. Aquí
no hay columna: el motor de invalidación de ``@api.depends`` que mantiene un
compute almacenado al día no está construido (tarea #191), y una columna que
nadie recalcula es peor que un cálculo en cada lectura — devuelve un valor
plausible y viejo. Mismo criterio que ``stock`` ya aplicó con
``StockPicking.date_deadline``.

**D-2 — ``reference_ids`` NO se declara aquí.** La fuente lo declara en los dos
lados del M2M (``purchase.order.reference_ids`` y
``stock.reference.purchase_ids``, ambos sobre ``stock_reference_purchase_rel``).
Django declara la relación **una vez** y genera el accesor inverso; declararla
dos veces produce dos tablas. Se declara en ``stock_reference.py`` de este mismo
addon con ``related_name='reference_ids'``, así que ``order.reference_ids`` se
lee igual que en la fuente. Es el mismo criterio y el mismo motivo que
``addons/stock/models/stock_reference.py`` documentó para ``move_ids``.

**D-3 — ``picking_type_id`` es ``required=True`` allá y opcional aquí.** La
fuente lo declara requerido con ``default=_default_picking_type``. Una columna
``NOT NULL`` sobre una tabla que **ya tiene filas** (``purchase_order`` existe y
se puebla) exigiría un valor para las existentes, y el valor por defecto
depende de que haya un tipo de operación de entrada sembrado — que este árbol
no garantiza. Se declara ``null=True`` y el ``default`` se conserva como
``_default_picking_type``, que sigue siendo el método que lo resuelve.
"""
from django.apps import apps

import fields
import models
from orm.environments import get_context
from orm.model_classes import extend_model

#: ≙ los tres estados de recepción (``odoo19c: :35-38``).
RECEIPT_PENDING = 'pending'
RECEIPT_PARTIAL = 'partial'
RECEIPT_FULL = 'full'
RECEIPT_STATUS_CHOICES = [
    (RECEIPT_PENDING, 'No recibida'),
    (RECEIPT_PARTIAL, 'Recibida parcialmente'),
    (RECEIPT_FULL, 'Recibida por completo'),
]


def _get_picking_type(cls, company_id):
    """≙ ``_get_picking_type`` (``odoo19c: :341-349``).

    El tipo de operación de entrada con el que se recibirá la mercancía. Las
    **tres** búsquedas de la fuente, en su orden, y por una razón que el código
    hace explícita: primero el del almacén de la empresa; si no hay, uno global
    (sin almacén); y si tampoco, uno global **archivado** —la fuente lo busca
    con ``active_test=False``, que es su forma de decir «prefiero uno
    desactivado a ninguno».
    """
    StockPickingType = apps.get_model('stock', 'StockPickingType')
    picking_type = StockPickingType.objects.filter(
        code='incoming', warehouse__company=company_id).first()
    if picking_type is None:
        picking_type = StockPickingType.objects.filter(
            code='incoming', warehouse__isnull=True, active=True).first()
    if picking_type is None:
        picking_type = StockPickingType.objects.filter(
            code='incoming', warehouse__isnull=True).first()
    return picking_type


def _default_picking_type(cls):
    """≙ ``_default_picking_type`` (``odoo19c: :16-17``).

    La empresa sale del contexto, con la de la sesión como respaldo — igual que
    ``self.env.context.get('company_id') or self.env.company.id``.
    """
    company_id = get_context().get('company_id')
    if company_id is None:
        ResCompany = apps.get_model('base', 'ResCompany')
        company_rec = ResCompany.objects.first()
        company_id = company_rec.pk if company_rec is not None else None
    return cls._get_picking_type(company_id)


def _compute_picking_ids(self):
    """≙ ``_compute_picking_ids`` (``odoo19c: :43-46``).

    Los albaranes de la orden son los de los movimientos de sus líneas.
    """
    StockPicking = apps.get_model('stock', 'StockPicking')
    return StockPicking.objects.filter(
        move_ids__purchase_line__order=self).distinct()


def picking_ids(self):
    """≙ ``picking_ids`` (``odoo19c: :21``) — D-1."""
    return self._compute_picking_ids()


def _compute_incoming_picking_count(self):
    """≙ ``_compute_incoming_picking_count`` (``odoo19c: :48-51``)."""
    return self._compute_picking_ids().count()


def incoming_picking_count(self):
    """≙ ``incoming_picking_count`` (``odoo19c: :20``)."""
    return self._compute_incoming_picking_count()


def _compute_effective_date(self):
    """≙ ``_compute_effective_date`` (``odoo19c: :53-57``).

    «Completion date of the first receipt order.» Sólo cuentan los albaranes
    hechos cuyo destino **no** es un proveedor: una devolución no es una
    llegada.
    """
    dates = [
        p.date_done for p in self._compute_picking_ids()
        if p.state == 'done' and p.date_done
        and p.location_dest is not None
        and p.location_dest.usage != 'supplier'
    ]
    return min(dates) if dates else None


def effective_date(self):
    """≙ ``effective_date`` (``odoo19c: :31-32``) — D-1."""
    return self._compute_effective_date()


def _compute_is_shipped(self):
    """≙ ``_compute_is_shipped`` (``odoo19c: :59-65``).

    La orden está servida cuando tiene albaranes y **todos** están hechos o
    cancelados.
    """
    pickings = list(self._compute_picking_ids())
    if not pickings:
        return False
    return all(p.state in ('done', 'cancel') for p in pickings)


def is_shipped(self):
    """≙ ``is_shipped`` (``odoo19c: :30``)."""
    return self._compute_is_shipped()


def _compute_receipt_status(self):
    """≙ ``_compute_receipt_status`` (``odoo19c: :67-77``).

    Las cuatro ramas de la fuente, en su orden: sin albaranes (o todos
    cancelados) no hay estado; todos hechos o cancelados es completa; alguno
    hecho es parcial; el resto, pendiente.
    """
    pickings = list(self._compute_picking_ids())
    if not pickings or all(p.state == 'cancel' for p in pickings):
        return None
    if all(p.state in ('done', 'cancel') for p in pickings):
        return RECEIPT_FULL
    if any(p.state == 'done' for p in pickings):
        return RECEIPT_PARTIAL
    return RECEIPT_PENDING


def receipt_status(self):
    """≙ ``receipt_status`` (``odoo19c: :35-41``)."""
    return self._compute_receipt_status()


def _compute_dest_address_id(self):
    """≙ ``_compute_dest_address_id`` (``odoo19c: :79-81``).

    La dirección de destino sólo tiene sentido cuando la operación entrega a un
    cliente (dropship). En cualquier otro caso la fuente la limpia; aquí el
    método **devuelve** si debe conservarse, y quien escriba el campo decide —
    misma traducción que el resto de ``_compute_`` de este archivo.
    """
    if self.picking_type_id is None:
        return None
    destination_loc = self.picking_type.default_location_dest
    if destination_loc is None or destination_loc.usage != 'customer':
        return None
    return self.dest_address


def default_location_dest_id_usage(self):
    """≙ ``default_location_dest_id_usage`` (``odoo19c: :25-26``).

    Campo técnico: ``related='picking_type_id.default_location_dest_id.usage'``.
    La fuente lo declara para que la vista sepa cuándo mostrar la dirección de
    dropship; aquí es una ``property`` porque un ``related`` sin ``store`` no
    tiene columna.
    """
    if self.picking_type_id is None:
        return None
    destination_loc = self.picking_type.default_location_dest
    return destination_loc.usage if destination_loc is not None else None


def _get_destination_location(self):
    """≙ ``_get_destination_location`` (``odoo19c: :324-328``).

    Dónde entra la mercancía: la ubicación de cliente de la dirección de
    destino si es un dropship, y si no la de destino del tipo de operación.
    """
    if self.dest_address_id and self.picking_type_id \
            and self.picking_type.code == 'dropship':
        return self.dest_address.property_stock_customer
    if self.picking_type_id is None:
        return None
    return self.picking_type.default_location_dest


def _get_final_location_record(self):
    """≙ ``_get_final_location_record`` (``odoo19c: :330-340``).

    El destino **final** de la cadena, que no siempre es el destino inmediato:
    con recepción en varios pasos la mercancía entra a un muelle y termina en
    la ubicación de existencias. La fuente elige el destino del tipo de
    operación sólo si cuelga del almacén; si no, el de existencias.
    """
    if self.picking_type_id is None:
        return None
    if self.picking_type.code == 'dropship':
        if self.dest_address_id:
            return self.dest_address.property_stock_customer
        return self.picking_type.default_location_dest
    warehouse = self.picking_type.warehouse
    wh_stock_loc = warehouse.lot_stock if warehouse is not None else None
    default_dest_loc = self.picking_type.default_location_dest
    if default_dest_loc is not None and (
            wh_stock_loc is None or default_dest_loc.child_of(wh_stock_loc)):
        return default_dest_loc
    return wh_stock_loc


def _prepare_reference_vals(self):
    """≙ ``_prepare_reference_vals`` (``odoo19c: :351-355``) — verbatim."""
    return {'name': self.name}


def _add_reference(self, reference):
    """≙ ``_add_reference`` (``odoo19c: :436-439``).

    Enlaza las referencias dadas. El comentario ``TODO`` de la fuente sobre el
    nombre del parámetro (singular por plural) se conserva en el nombre para no
    divergir de la firma que sus llamadores usan.
    """
    self.reference_ids.add(*reference)


def _remove_reference(self, reference):
    """≙ ``_remove_reference`` (``odoo19c: :441-444``)."""
    self.reference_ids.remove(*reference)


def _is_display_stock_in_catalog(self):
    """≙ ``_is_display_stock_in_catalog`` (``odoo19c: :414-415``) — verbatim.

    Punto de extensión: el catálogo de productos de una compra **sí** muestra
    existencias. La fuente devuelve ``True`` a secas.
    """
    return True


def apply_purchase_stock_purchase_order_extensions():
    """Cuelga sobre ``purchase.PurchaseOrder`` lo que ``purchase_stock`` le
    añade — ≙ ``_inherit``."""
    extend_model(
        'purchase', 'PurchaseOrder',
        campos={
            'incoterm_location': fields.Char(
                max_length=255, blank=True, default='',
                verbose_name='Lugar del Incoterm',
                help_text='Lugar al que se refiere el Incoterm de la compra '
                          '(Odoo incoterm_location).',
            ),
            'picking_type': fields.Many2one(
                'stock.StockPickingType', null=True, blank=True,
                on_delete=models.PROTECT, related_name='purchase_orders',
                verbose_name='Entregar en',
                help_text='Determina el tipo de operación de la recepción '
                          '(Odoo picking_type_id). D-3: opcional aquí, '
                          'requerido en la referencia.',
            ),
            'dest_address': fields.Many2one(
                'base.ResPartner', null=True, blank=True,
                on_delete=models.SET_NULL,
                related_name='dropship_purchase_orders',
                verbose_name='Dirección de destino',
                help_text='Dirección a la que se envía directamente cuando la '
                          'operación es dropship (Odoo dest_address_id).',
            ),
        },
        propiedades={
            'picking_ids': picking_ids,
            'incoming_picking_count': incoming_picking_count,
            'effective_date': effective_date,
            'is_shipped': is_shipped,
            'receipt_status': receipt_status,
            'default_location_dest_id_usage': default_location_dest_id_usage,
        },
        metodos={
            '_compute_picking_ids': _compute_picking_ids,
            '_compute_incoming_picking_count': _compute_incoming_picking_count,
            '_compute_effective_date': _compute_effective_date,
            '_compute_is_shipped': _compute_is_shipped,
            '_compute_receipt_status': _compute_receipt_status,
            '_compute_dest_address_id': _compute_dest_address_id,
            '_get_destination_location': _get_destination_location,
            '_get_final_location_record': _get_final_location_record,
            '_prepare_reference_vals': _prepare_reference_vals,
            '_add_reference': _add_reference,
            '_remove_reference': _remove_reference,
            '_is_display_stock_in_catalog': _is_display_stock_in_catalog,
        },
        luego=_install_class,
    )


def _install_class(model):
    """Los dos ``@api.model`` de la fuente y el vocabulario de recepción.

    ``_get_picking_type`` y ``_default_picking_type`` son ``@api.model`` allá y
    **``@classmethod`` aquí**: ``_default_picking_type`` llama a
    ``cls._get_picking_type(...)``, así que si el segundo se instalara de
    instancia la llamada reventaría sólo al ejecutarse (``H-API-738``).
    """
    if not hasattr(model, '_get_picking_type'):
        model._get_picking_type = classmethod(_get_picking_type)
    if not hasattr(model, '_default_picking_type'):
        model._default_picking_type = classmethod(_default_picking_type)
    if not hasattr(model, 'RECEIPT_STATUS_CHOICES'):
        model.RECEIPT_PENDING = RECEIPT_PENDING
        model.RECEIPT_PARTIAL = RECEIPT_PARTIAL
        model.RECEIPT_FULL = RECEIPT_FULL
        model.RECEIPT_STATUS_CHOICES = RECEIPT_STATUS_CHOICES
