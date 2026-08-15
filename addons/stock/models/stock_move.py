"""Modelo ``StockMove`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_move.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

El movimiento es la unidad de intención del inventario: dice **qué producto**,
**cuánto**, **de dónde** y **a dónde**, y en qué estado está esa intención. La
ejecución real la llevan sus líneas (``stock.move.line``), que son las que
tocan las existencias; el movimiento agrega, encadena y decide.

Porte en DOS PASES — este archivo es el primero
=================================================

Medido sobre ``odoo19c: addons/stock/models/stock_move.py`` (2825 líneas):
**74 campos y 131 métodos**. El grafo de ``stock`` es un **ciclo** y se rompe
partiéndolo, según el orden que fija :ref:`h-api-601`:

===  =========================  ====================================================
#    Archivo                    Qué aporta
===  =========================  ====================================================
1    ``stock_reference.py``     cerrado — desbloquea ``reference_ids``
2    **este pase**              los **73 campos** declarables (74 menos uno)
3    ``product.py``             los 7 símbolos que el orderpoint consume
4    ``stock_orderpoint.py``    consume el paso 3
5    segundo pase de este       ``orderpoint_id`` + los métodos que lo consumen
===  =========================  ====================================================

**Por qué ``orderpoint_id`` no está aquí, y no es una omisión silenciosa.**
``stock.warehouse.orderpoint`` **no existe en este árbol** — medido:
``grep -rn "class .*Orderpoint" addons/ src/`` → **0**. Una FK por cadena es
perezosa en el *orden de resolución*, no en la *existencia* del destino: Django
emite ``fields.E300`` cuando el modelo no está instalado, y el commit
``07044d3`` lo midió con 18 errores por exactamente esa causa. El campo entra en
el paso 5, cuando el paso 4 haya aterrizado. Sucesores: tareas **#257** y
**#330**.

Los 73 campos de este pase
============================

Convención del árbol: una FK pierde el sufijo ``_id`` (``location_id`` →
``location``); una colección lo conserva (``move_line_ids``). Un campo que la
referencia declara ``compute=`` **sin** ``store=`` se porta como **property** —
su ORM lo recalcula en cada lectura y nunca lo persiste, que es lo que una
property ya hace. Los ``compute=`` **con** ``store=`` sí son columna, y los
invoca ``save()`` (ver :ref:`h-api-591`).

Escalares y relaciones almacenadas (columna real)
---------------------------------------------------

``sequence`` · ``priority`` · ``date`` · ``date_deadline`` · ``company`` ·
``product`` · ``never_product_template_attribute_value_ids`` ·
``description_picking_manual`` · ``product_qty`` · ``product_uom_qty`` ·
``product_uom`` · ``location`` · ``location_dest`` · ``location_final`` ·
``partner`` · ``move_orig_ids`` · ``picking`` · ``state`` · ``picked`` ·
``price_unit`` · ``origin`` · ``procure_method`` · ``scrap`` · ``rule`` ·
``propagate_cancel`` · ``delay_alert_date`` · ``picking_type`` ·
``is_inventory`` · ``inventory_name`` · ``origin_returned_move`` ·
``restrict_partner`` · ``route_ids`` · ``warehouse`` · ``quantity`` ·
``additional`` · ``reference`` · ``next_serial`` · ``next_serial_count`` ·
``reservation_date`` · ``packaging_uom`` · ``packaging_uom_qty``

Derivados (property — ``compute`` sin ``store`` en la fuente)
---------------------------------------------------------------

``product_category`` · ``description_picking`` · ``allowed_uom_ids`` ·
``product_tmpl`` · ``location_usage`` · ``location_dest_usage`` ·
``move_dest_ids`` · ``package_ids`` · ``returned_move_ids`` · ``availability`` ·
``has_tracking`` · ``has_lines_without_result_package`` · ``show_operations`` ·
``picking_code`` · ``show_details_visible`` · ``is_storable`` · ``is_locked`` ·
``is_initial_demand_editable`` · ``is_date_editable`` ·
``is_quantity_done_editable`` · ``move_lines_count`` · ``display_assign_serial``
· ``display_import_lot`` · ``forecast_availability`` ·
``forecast_expected_date`` · ``lot_ids`` · ``show_quant`` · ``show_lots_m2o`` ·
``show_lots_text`` · ``move_line_ids`` (inverso) · ``reference_ids`` (inverso)

Divergencias declaradas en este pase
======================================

**D-1 — ``procurement_values`` no es columna.** La referencia lo declara
``fields.Json(store=False, help="Dummy field to store procurement values to
propagate them to later steps")``. Es un portapapeles entre pasos de una misma
transacción, no un dato del movimiento; aquí es un atributo de instancia con
property, que es lo mismo sin tabla de por medio.

**D-2 — ``move_orig_ids`` renombrado desde ``move_orig``.** El campo existía con
el nombre truncado y su ``related_name`` era ``move_dest``. La referencia los
llama ``move_orig_ids``/``move_dest_ids`` y la convención de este árbol conserva
el sufijo en las colecciones (``move_line_ids``, ``route_ids``). Corregido en
este pase — estado incorrecto heredado, Clausula 2.

**D-3 — ``state`` gana ``partially_available``.** Nuestro Selection tenía seis
valores y la referencia declara **siete** (``odoo19c: :106-113``). El ausente lo
consume la agregación de cantidades del producto
(``('state', 'in', (…, 'partially_available'))``, ``product.py:212``) y lo
escribe ``_recompute_state``; sin él, el paso 3 no puede portarse fiel. La
referencia lo menciona **26** veces en este mismo archivo.

**D-4 — los 131 métodos son del paso 5.** Este pase conserva los cuatro que ya
existían (``_action_confirm``, ``_action_assign``, ``_action_done``,
``_action_cancel``) porque tienen consumidores vivos, y no añade los otros 127:
la mayoría consume ``product.virtual_available``/``free_qty`` (paso 3) o el
orderpoint (paso 4). Declararlos aquí a medias sería el porte parcial silencioso
que ``porte-completo-no-parcial.md`` prohíbe. Sucesor: tarea **#330**, paso 5.
"""
from decimal import Decimal

from django.apps import apps
from django.utils import timezone

import fields
import models

from orm.environments import get_current_company

from addons.stock.models.stock_quant import StockQuant
from addons.base.models import TimeStampedModel

#: ≙ ``PROCUREMENT_PRIORITIES`` (``odoo19c: stock_move.py:15``).
PROCUREMENT_PRIORITIES = [('0', 'Normal'), ('1', 'Urgent')]

#: ≙ ``_product_location_index`` (``:200``) — objeto de tabla, no atributo de
#: ORM: su hogar aquí es ``Meta.indexes``, con el nombre de la fuente.
PRODUCT_LOCATION_INDEX = models.Index(
    fields=['product', 'location', 'location_dest', 'company', 'state'],
    name='stock_move_product_location_idx',
)


class StockMove(TimeStampedModel):
    """``stock.move`` — un movimiento de inventario."""

    # Atributos de clase de modelo — los cuatro de ORM que la referencia
    # declara (``odoo19c: addons/stock/models/stock_move.py:19-22``), verbatim.
    # El quinto (``_product_location_index``) es un objeto de tabla y vive en
    # ``Meta.indexes``, que apunta al mismo objeto.
    _name = 'stock.move'
    _description = "Stock Move"
    _order = 'sequence, id'
    _rec_name = 'reference'
    _product_location_index = PRODUCT_LOCATION_INDEX

    PRIORITY_CHOICES = PROCUREMENT_PRIORITIES

    PROCURE_MAKE_TO_STOCK = 'make_to_stock'
    PROCURE_MAKE_TO_ORDER = 'make_to_order'
    PROCURE_METHOD_CHOICES = [
        (PROCURE_MAKE_TO_STOCK, 'Default: Take From Stock'),
        (PROCURE_MAKE_TO_ORDER, 'Advanced: Apply Procurement Rules'),
    ]

    # Los SIETE estados de la referencia (``:106-113``). ``partially_available``
    # faltaba: lo consume la agregación de cantidades del producto y lo escribe
    # ``_recompute_state`` (D-3 del docstring).
    STATE_DRAFT               = 'draft'
    STATE_WAITING             = 'waiting'
    STATE_CONFIRMED           = 'confirmed'
    STATE_PARTIALLY_AVAILABLE = 'partially_available'
    STATE_ASSIGNED            = 'assigned'
    STATE_DONE                = 'done'
    STATE_CANCEL              = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Nuevo'),
        (STATE_WAITING, 'Esperando otro movimiento'),
        (STATE_CONFIRMED, 'Esperando disponibilidad'),
        (STATE_PARTIALLY_AVAILABLE, 'Parcialmente disponible'),
        (STATE_ASSIGNED, 'Disponible'),
        (STATE_DONE, 'Hecho'),
        (STATE_CANCEL, 'Cancelado'),
    ]

    # --- identificación y agenda -------------------------------------------

    sequence        = fields.Integer(
        default=10, help_text='Orden dentro del albarán (Odoo sequence).',
    )
    priority        = fields.Selection(
        max_length=1, choices=PRIORITY_CHOICES, default='0',
        help_text='Prioridad (Odoo priority, compute+store desde el albarán).',
    )
    date            = fields.Datetime(
        db_index=True, default=timezone.now,
        help_text='Fecha planificada hasta que se hace; después, la real '
                  '(Odoo date, requerido, default=Datetime.now).',
    )
    date_deadline   = fields.Datetime(
        null=True, blank=True,
        help_text='Fecha límite propagada por la cadena (Odoo date_deadline, '
                  'readonly; lo escribe _set_date_deadline).',
    )
    reservation_date = fields.Date(
        null=True, blank=True,
        help_text='Fecha a partir de la cual reservar (Odoo reservation_date, '
                  'compute+store desde el tipo de operación).',
    )
    delay_alert_date = fields.Datetime(
        null=True, blank=True,
        help_text='Fecha de alerta por retraso de un movimiento origen '
                  '(Odoo delay_alert_date, compute+store).',
    )

    # --- qué se mueve --------------------------------------------------------

    company         = fields.Many2one(
        'base.ResCompany', on_delete=models.PROTECT, db_index=True,
        related_name='stock_moves', default=get_current_company,
        help_text='Empresa (Odoo company_id, requerido, '
                  'default=lambda self: self.env.company).',
    )
    product         = fields.Many2one(
        'product.ProductProduct', on_delete=models.PROTECT, related_name='stock_moves',
        db_index=True, help_text='Producto (Odoo product_id; el dominio excluye servicios).',
    )
    never_product_template_attribute_value_ids = fields.Many2many(
        'product.ProductTemplateAttributeValue', blank=True,
        related_name='stock_moves',
        db_table='template_attribute_value_stock_move_rel',
        help_text='Valores de atributo excluidos (Odoo '
                  'never_product_template_attribute_value_ids).',
    )
    product_uom     = fields.Many2one(
        'uom.Uom', on_delete=models.PROTECT, null=True, blank=True,
        related_name='stock_moves',
        help_text='Unidad del movimiento (Odoo product_uom, compute+store con '
                  'readonly=False; la recalcula compute_product_uom).',
    )
    product_uom_qty = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='Cantidad demandada, en la unidad del movimiento (Odoo '
                  'product_uom_qty). Bajarla NO genera pedido pendiente.',
    )
    product_qty     = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='La misma demanda en la unidad del PRODUCTO (Odoo '
                  'product_qty, compute+store; su inverso lanza error a '
                  'propósito — se escribe product_uom_qty).',
    )
    quantity        = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='Suma de las cantidades de las líneas (Odoo quantity, '
                  'compute+store con inverso).',
    )
    packaging_uom   = fields.Many2one(
        'uom.Uom', on_delete=models.PROTECT, null=True, blank=True,
        related_name='stock_moves_packaging',
        help_text='Unidad de empaque de la orden de origen (Odoo '
                  'packaging_uom_id, compute+store precompute).',
    )
    packaging_uom_qty = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='La demanda en la unidad de empaque (Odoo '
                  'packaging_uom_qty, compute+store).',
    )
    price_unit      = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0000'),
        help_text='Coste unitario fijado al confirmar, en la divisa de la '
                  'empresa (Odoo price_unit; campo técnico, sin digits).',
    )

    # --- de dónde a dónde ----------------------------------------------------

    location        = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, related_name='moves_out',
        db_index=True, help_text='Ubicación origen (Odoo location_id, compute+store).',
    )
    location_dest   = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, related_name='moves_in',
        db_index=True,
        help_text='Ubicación destino INTERMEDIA (Odoo location_dest_id, '
                  'compute+store con inverso).',
    )
    location_final  = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, null=True, blank=True,
        related_name='moves_final', db_index=True,
        help_text='Ubicación destino FINAL de la cadena (Odoo '
                  'location_final_id). El destino intermedio es el siguiente '
                  'salto; éste es el fin del encargo.',
    )
    warehouse       = fields.Many2one(
        'stock.StockWarehouse', on_delete=models.PROTECT, null=True, blank=True,
        related_name='stock_moves',
        help_text='Almacén a considerar al elegir ruta en el siguiente '
                  'aprovisionamiento (Odoo warehouse_id).',
    )
    route_ids       = fields.Many2many(
        'stock.StockRoute', blank=True, related_name='stock_moves',
        db_table='stock_route_move',
        help_text='Rutas de destino preferidas (Odoo route_ids).',
    )
    partner         = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_moves',
        help_text='Dirección de entrega opcional (Odoo partner_id, '
                  'compute+store desde el albarán).',
    )
    restrict_partner = fields.Many2one(
        'base.ResPartner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='stock_moves_restricted',
        help_text='Propietario cuyos quants son los únicos considerables al '
                  'marcar hecho (Odoo restrict_partner_id).',
    )

    # --- documentos y encadenamiento -----------------------------------------

    picking         = fields.Many2one(
        'stock.StockPicking', null=True, blank=True, on_delete=models.CASCADE,
        related_name='move_ids', db_index=True,
        help_text='Transferencia (Odoo picking_id).',
    )
    picking_type    = fields.Many2one(
        'stock.StockPickingType', null=True, blank=True, on_delete=models.PROTECT,
        related_name='stock_moves',
        help_text='Tipo de operación (Odoo picking_type_id, compute+store con '
                  'readonly=False).',
    )
    rule            = fields.Many2one(
        'stock.StockRule', null=True, blank=True, on_delete=models.PROTECT,
        related_name='stock_moves',
        help_text='Regla que creó el movimiento (Odoo rule_id, '
                  "ondelete='restrict').",
    )
    move_orig_ids   = fields.Many2many(
        'self', symmetrical=False, blank=True, related_name='move_dest_ids',
        db_table='stock_move_move_rel',
        help_text='Movimientos origen que abastecen a éste (Odoo '
                  'move_orig_ids). El inverso es move_dest_ids, el nombre que '
                  'la referencia le da a la otra mitad.',
    )
    origin_returned_move = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='returned_move_ids', db_index=True,
        help_text='Movimiento que originó esta devolución (Odoo '
                  'origin_returned_move_id).',
    )
    scrap           = fields.Many2one(
        'stock.StockScrap', null=True, blank=True, on_delete=models.CASCADE,
        related_name='move_ids',
        help_text='Desecho que originó el movimiento (Odoo scrap_id). Es el '
                  'inverso que ``stock.scrap.move_ids`` declara '
                  '(odoo19c: stock/models/stock_scrap.py:37).',
    )
    origin          = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Documento de origen, en texto (Odoo origin).',
    )
    reference       = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Etiqueta del movimiento (Odoo reference, compute+store). '
                  'Es el _rec_name: sale del albarán, del desecho o del '
                  'nombre de inventario, en ese orden.',
    )

    # --- estado y banderas ---------------------------------------------------

    state           = fields.Selection(
        max_length=20, choices=STATE_CHOICES, default=STATE_DRAFT, db_index=True,
        help_text='Estado (Odoo state, readonly). Los SIETE de la referencia.',
    )
    picked          = fields.Boolean(
        default=False,
        help_text='Marca indicativa de recogido (Odoo picked, compute+store '
                  'con inverso). No valida ni genera movimientos por sí sola.',
    )
    procure_method  = fields.Selection(
        max_length=16, choices=PROCURE_METHOD_CHOICES, default=PROCURE_MAKE_TO_STOCK,
        help_text='Método de suministro (Odoo procure_method). make_to_stock '
                  'espera disponibilidad; make_to_order dispara una regla.',
    )
    propagate_cancel = fields.Boolean(
        default=True,
        help_text='Si al cancelar éste se cancela el movimiento enlazado '
                  '(Odoo propagate_cancel).',
    )
    is_inventory    = fields.Boolean(
        default=False,
        help_text='El movimiento es un ajuste de inventario (Odoo is_inventory).',
    )
    inventory_name  = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Nombre del ajuste (Odoo inventory_name, readonly).',
    )
    additional      = fields.Boolean(
        default=False,
        help_text='El movimiento se añadió DESPUÉS de confirmar el albarán '
                  '(Odoo additional).',
    )
    description_picking_manual = fields.Text(
        blank=True, default='',
        help_text='Descripción escrita a mano (Odoo '
                  'description_picking_manual, readonly). Cuando está, gana '
                  'sobre la derivada del producto.',
    )
    next_serial     = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Primer número de serie a generar (Odoo next_serial).',
    )
    next_serial_count = fields.Integer(
        default=0,
        help_text='Cuántos números de serie generar (Odoo next_serial_count).',
    )

    class Meta:
        db_table = 'stock_move'
        ordering = ['sequence', 'id']
        verbose_name = 'Movimiento de inventario'
        verbose_name_plural = 'Movimientos de inventario'
        indexes = [PRODUCT_LOCATION_INDEX]

    def __str__(self) -> str:
        return f'{self.product} {self.product_uom_qty} [{self.state}]'

    # --- derivados: los ``compute`` sin ``store`` de la referencia -----------

    @property
    def product_category(self):
        """Categoría del producto (≙ ``product_category_id``, related)."""
        return self.product.categ if self.product_id else None

    @property
    def product_tmpl(self):
        """Plantilla del producto (≙ ``product_tmpl_id``, related)."""
        return self.product.product_tmpl if self.product_id else None

    @property
    def location_usage(self):
        """Tipo de la ubicación origen (≙ ``location_usage``, related)."""
        return self.location.usage if self.location_id else None

    @property
    def location_dest_usage(self):
        """Tipo de la ubicación destino (≙ ``location_dest_usage``, related)."""
        return self.location_dest.usage if self.location_dest_id else None

    @property
    def has_tracking(self):
        """Trazabilidad del producto (≙ ``has_tracking``, related)."""
        return self.product.tracking if self.product_id else None

    @property
    def is_storable(self):
        """¿El producto lleva existencias? (≙ ``is_storable``, related)."""
        return bool(self.product.is_storable) if self.product_id else False

    @property
    def picking_code(self):
        """Código del tipo de operación (≙ ``picking_code``, related)."""
        return self.picking_type.code if self.picking_type_id else None

    @property
    def show_operations(self):
        """≙ ``show_operations`` (related del tipo de operación del albarán)."""
        return bool(self.picking_type.show_operations) if self.picking_type_id else False

    @property
    def allowed_uom_ids(self):
        """Unidades admisibles para este movimiento (≙ ``_compute_allowed_uom_ids``).

        La fuente une tres conjuntos: la unidad del producto, sus empaquetados
        y las unidades de sus proveedores. Los tres los declara
        ``product.template``, así que se leen por el delegado (``product_tmpl``)
        — la variante no los tiene propios.
        """
        if not self.product_id:
            return apps.get_model('uom', 'Uom').objects.none()
        Uom = apps.get_model('uom', 'Uom')
        tmpl = self.product.product_tmpl
        ids = {tmpl.uom_id} if tmpl.uom_id else set()   # FK sin traer la fila
        ids |= set(tmpl.uom_ids.values_list('pk', flat=True))
        ids |= set(tmpl.seller_ids.exclude(product_uom__isnull=True)
                   .values_list('product_uom', flat=True))
        return Uom.objects.filter(pk__in=ids)

    @property
    def move_lines_count(self) -> int:
        """Número de líneas (≙ ``_compute_move_lines_count``)."""
        return self.move_line_ids.count()

    @property
    def is_initial_demand_editable(self) -> bool:
        """≙ ``_compute_is_initial_demand_editable``."""
        return (not self.picking.is_locked if self.picking_id else True) \
            or self.state == self.STATE_DRAFT

    @property
    def is_date_editable(self) -> bool:
        """≙ ``_compute_is_date_editable``."""
        return self.picking.is_date_editable if self.picking_id else True

    @property
    def is_quantity_done_editable(self) -> bool:
        """≙ ``_compute_is_quantity_done_editable``."""
        return bool(self.product_id)

    @property
    def is_locked(self) -> bool:
        """≙ ``_compute_is_locked`` — sin albarán, nunca bloqueado."""
        return bool(self.picking.is_locked) if self.picking_id else False

    @property
    def has_lines_without_result_package(self) -> bool:
        """≙ ``_compute_has_lines_without_result_package``.

        Cierto sólo si **alguna** línea ya tiene paquete de destino y **otra**
        no — un movimiento sin ningún paquete no cuenta.
        """
        lineas = list(self.move_line_ids.all())
        return any(l.result_package_id for l in lineas) and \
            any(not l.result_package_id for l in lineas)

    @property
    def display_import_lot(self) -> bool:
        """≙ ``_compute_display_assign_serial`` (la primera de las dos salidas)."""
        return bool(
            self.has_tracking and self.has_tracking != 'none'
            and self.product_id
            and self.picking_type_id and self.picking_type.use_create_lots
            and not self.origin_returned_move_id
            and self.state not in (self.STATE_DONE, self.STATE_CANCEL)
        )

    @property
    def display_assign_serial(self) -> bool:
        """≙ ``_compute_display_assign_serial`` — la fuente iguala ambas."""
        return self.display_import_lot

    @property
    def show_quant(self) -> bool:
        """≙ ``_compute_show_info`` (primera de sus tres salidas)."""
        return self.picking_code != 'incoming' and self.is_storable

    @property
    def show_lots_text(self) -> bool:
        """≙ ``_compute_show_info`` (segunda salida)."""
        return bool(
            self.has_tracking and self.has_tracking != 'none'
            and self.picking_type_id and self.picking_type.use_create_lots
            and not self.picking_type.use_existing_lots
            and self.state != self.STATE_DONE
            and not self.origin_returned_move_id
        )

    @property
    def show_lots_m2o(self) -> bool:
        """≙ ``_compute_show_info`` (tercera salida)."""
        return bool(
            not self.show_quant and not self.show_lots_text
            and self.has_tracking and self.has_tracking != 'none'
            and ((self.picking_type_id and self.picking_type.use_existing_lots)
                 or self.state == self.STATE_DONE
                 or self.origin_returned_move_id)
        )

    @property
    def availability(self):
        """Cantidad aún reservable (≙ ``_compute_product_availability``).

        Hecho el movimiento, es lo que movió de verdad; antes, el mínimo entre
        la demanda y lo disponible en la ubicación origen.
        """
        if self.state == self.STATE_DONE:
            return self.product_qty
        if not self.product_id:
            return Decimal('0.0000')
        return min(self.product_qty,
                   StockQuant.available_qty(self.product, self.location))

    @property
    def procurement_values(self):
        """Portapapeles entre pasos del aprovisionamiento (≙ ``procurement_values``).

        La referencia lo declara ``fields.Json(store=False)`` y su propio
        ``help`` lo llama *dummy field*: no es un dato del movimiento, es un
        valor que viaja entre pasos de la misma transacción. Aquí es atributo de
        instancia — lo mismo, sin columna (D-1 del docstring).
        """
        return getattr(self, '_procurement_values', None)

    @procurement_values.setter
    def procurement_values(self, value):
        self._procurement_values = value

    @property
    def description_picking(self):
        """Descripción para el albarán (≙ ``_compute_description_picking``).

        La manual gana; si no la hay, se deriva del producto. El inverso de la
        fuente (``_inverse_description_picking``) es el setter.
        """
        if self.description_picking_manual:
            return self.description_picking_manual
        if not self.product_id:
            return ''
        return self.product._get_picking_description(self.picking_type) \
            or self._get_description()

    @description_picking.setter
    def description_picking(self, value):
        self.description_picking_manual = value

    def _get_description(self) -> str:
        """≙ ``_get_description`` — la descripción del producto para este tipo."""
        return self.product._get_description(self.picking_type) if self.product_id else ''

    # --- máquina de estados (los cuatro con consumidores vivos) --------------

    def _action_confirm(self):
        """Confirma el movimiento (≙ ``_action_confirm``).

        Con orígenes pendientes → ``waiting`` (MTO); sin ellos → ``confirmed``.
        """
        if self.state in (self.STATE_DONE, self.STATE_CANCEL):
            return self
        has_pending_orig = self.move_orig_ids.exclude(state=self.STATE_DONE).exists()
        self.state = self.STATE_WAITING if has_pending_orig else self.STATE_CONFIRMED
        self.save(update_fields=['state', 'updated_at'])
        return self

    def _action_assign(self):
        """Reserva la disponibilidad (≙ ``_action_assign``).

        Reserva desde el stock disponible en la ubicación origen (``StockQuant``):
        ``quantity`` = min(demanda, disponible). Si cubre la demanda →
        ``assigned``; si cubre una parte → ``partially_available``, el séptimo
        estado que este pase repone (D-3).
        """
        if self.state not in (self.STATE_CONFIRMED, self.STATE_WAITING,
                              self.STATE_PARTIALLY_AVAILABLE, self.STATE_ASSIGNED):
            return self
        available = StockQuant.available_qty(self.product, self.location)
        self.quantity = min(self.product_uom_qty, available)
        if self.product_uom_qty > 0:
            if self.quantity >= self.product_uom_qty:
                self.state = self.STATE_ASSIGNED
            elif self.quantity > 0:
                self.state = self.STATE_PARTIALLY_AVAILABLE
        self.save(update_fields=['quantity', 'state', 'updated_at'])
        return self

    def _action_done(self):
        """Ejecuta el movimiento (≙ ``_action_done``): aplica los quants."""
        if self.state == self.STATE_CANCEL:
            return self
        done_qty = self.quantity or self.product_uom_qty
        StockQuant.apply_move(self.product, self.location, self.location_dest, done_qty)
        self.quantity = done_qty
        self.state = self.STATE_DONE
        self.save(update_fields=['quantity', 'state', 'updated_at'])
        return self

    def _action_cancel(self):
        """Cancela el movimiento (≙ ``_action_cancel``)."""
        if self.state == self.STATE_DONE:
            return self
        self.state = self.STATE_CANCEL
        self.quantity = Decimal('0.0000')
        self.save(update_fields=['state', 'quantity', 'updated_at'])
        return self
