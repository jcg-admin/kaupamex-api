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

**D-4 — los 131 métodos se portan por olas.** Este archivo es el mayor de la
familia: **2825 líneas** en la referencia contra las nuestras. El porte va por
olas, y cada una declara su cobertura aquí en vez de presentarse como cerrada.

Cobertura de métodos — medida, no estimada
============================================

El instrumento es el conteo por AST **normalizado**: un ``_compute_x`` cuenta
como cubierto si ``x`` existe aquí como property o como columna, porque ésa es
la forma que este árbol le da a un ``compute`` sin ``store`` (precedente en todo
el addon). Sin esa normalización el conteo crudo reporta 126 ausentes y **34 de
ellos son falsos** — es la ceguera que :ref:`h-api-579` registra.

.. list-table::
   :header-rows: 1

   * - Ola
     - Qué entra
     - Métodos
   * - —
     - los cuatro de acción que ya existían
     - 4
   * - —
     - computes portados como property (normalización de arriba)
     - 30
   * - A
     - predicados, ayudantes puros, recorrido de cadena, ``_recompute_state``
     - 40
   * - **B** (este pase)
     - persistencia y propagación a reglas de reabastecimiento
     - **9**
   * - C
     - reserva y disponibilidad: ``_update_reserved_quantity`` y su familia
     - 12
   * - D
     - fusión, división y asignación de albarán
     - 18
   * - E
     - lotes y números de serie
     - 8
   * - F
     - previsión, empuje, abastecimiento y las acciones de ventana
     - 14

**Estado tras la ola B: 83 de 131** — remedido con el instrumento de arriba, no
sumado. Las olas C–F son la tarea **#390**; ninguna se difiere sin dueño.

**Uno de los 83 está portado a medias, y se dice aquí:** ``write`` tiene sus dos
guardas (cantidad de un cancelado, unidad de un hecho) y la propagación a las
reglas de reabastecimiento, pero **no** el des-reservar/re-asignar de
``product_uom_qty`` (``odoo19c: :851-871``) ni el re-cálculo de almacén
(``:891-899``). Ésos cuelgan de ``_do_unreserve`` y ``_action_assign``, que son
la ola C; portar media mitad ahora dejaría un mecanismo a medio armar sin nadie
que lo note. Es la cobertura declarada que ``porte-completo-no-parcial.md``
exige en vez del silencio.

Qué entró en la ola B
-----------------------

``default_get`` · ``create`` (con ``_normalize_create_values``, la parte pura
separada para poder probarla sin insertar) · ``write`` (parcial, arriba) ·
``unlink`` · ``_set_references`` · ``_compute_display_name`` (como property
``display_name``) · ``_update_orderpoints`` · ``_get_orderpoints_to_update`` ·
``_delay_alert_get_documents`` · ``_propagate_date_log_note``.

Dos piezas que la ola B tuvo que traer de fuera, porque sin ellas el porte
habría necesitado inventar una divergencia:

- ``stock.picking.origin`` (``odoo19c: stock_picking.py:556-558``) — lo lee
  ``_compute_display_name``. Migración ``0012_add_picking_origin``.
- ``stock.picking.reference_ids`` (``related``, ``:590-591``) — lo lee
  ``_set_references``; property, porque allá no tiene columna.

Y una divergencia de mecanismo, declarada: ``_mark_orderpoints_for_recompute``
es el ``add_to_compute`` de la fuente hecho explícito. Allá el ORM difiere el
cálculo hasta la próxima lectura; este ORM no tiene cola de cómputo diferido
(tarea **#191**), así que se ejecuta ya. Misma cifra, distinto cuándo.

Por qué la ola A va primero, y no las acciones
------------------------------------------------

Los cuarenta símbolos de la ola A **no dependen de ninguna pieza ausente**: son
predicados sobre campos que ya existen, ayudantes puros y el recorrido de la
cadena. Las olas siguientes los consumen —``_recompute_state`` lo llaman cinco
métodos de la ola D, ``_rollup_moves`` lo llaman tres de la F—, así que
portarlos primero evita escribirlos dos veces.

El mismo criterio reordenó el archivo: ``stock_picking.py`` iba antes en el
plan, y su orquestación llama a doce métodos de este archivo. Portarlo primero
habría producido una docena de BLOQUEADOS que la ola siguiente tendría que
retocar de inmediato. Prevalece el análisis actual (Clausula 1).
"""
import re
from decimal import Decimal

from django.apps import apps
from django.utils import timezone

import fields
import models

from orm.environments import get_current_company, get_current_user
from tools.float_utils import float_compare
from tools.translate import _
from exceptions import UserError

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

    # --- Ola A: predicados, ayudantes puros y recorrido de cadena ---------
    #
    # Los cuarenta símbolos de este bloque comparten una propiedad: **no
    # dependen de ninguna pieza ausente**. Se portan verbatim de la referencia
    # y quedan disponibles para las olas siguientes, que sí orquestan.

    def _quantity_sml(self):
        """≙ ``_quantity_sml`` (``odoo19c: :401-406``).

        La suma de las cantidades de las líneas, convertida a la unidad del
        movimiento. Sin redondear — la fuente pasa ``round=False`` a propósito:
        redondear aquí perdería el resto que la comparación posterior necesita.
        """
        cantidad = Decimal('0')
        for linea in self.move_line_ids.all():
            cantidad += linea.product_uom._compute_quantity(
                linea.quantity, self.product_uom, round=False)
        return cantidad

    def _visible_quantity(self):
        """≙ ``_visible_quantity`` (``odoo19c: :2811-2813``)."""
        return self.quantity

    def _is_incoming(self):
        """≙ ``_is_incoming`` (``odoo19c: :2815-2819``).

        Entra mercancía cuando el origen es externo: cliente, proveedor, o un
        tránsito **sin empresa** (el tránsito de una empresa nuestra es
        interno, no una entrada).
        """
        origen = self.location
        if origen is None:
            return False
        return origen.usage in ('customer', 'supplier') or (
            origen.usage == 'transit' and origen.company_id is None
        )

    def _is_outgoing(self):
        """≙ ``_is_outgoing`` (``odoo19c: :2821-2825``) — el simétrico."""
        destino = self.location_dest
        if destino is None:
            return False
        return destino.usage in ('customer', 'supplier') or (
            destino.usage == 'transit' and destino.company_id is None
        )

    def _is_consuming(self):
        """≙ ``_is_consuming`` (``odoo19c: :2433-2437``).

        Consume existencias si es interno/salida, o si cruza de un almacén a
        otro distinto.
        """
        wh_origen = self.location.warehouse if self.location_id else None
        wh_destino = self.location_dest.warehouse if self.location_dest_id else None
        if self.picking_code in ('internal', 'outgoing'):
            return True
        return bool(wh_origen and wh_destino and wh_origen != wh_destino)

    def _should_bypass_reservation(self, forced_location=None):
        """≙ ``_should_bypass_reservation`` (``odoo19c: :1962-1965``).

        Se salta la reserva si la ubicación lo permite (proveedor, cliente,
        inventario…) o si el producto no lleva existencias.
        """
        ubicacion = forced_location or self.location
        if ubicacion is not None and ubicacion.should_bypass_reservation():
            return True
        return not self.is_storable

    def _should_assign_at_confirm(self):
        """≙ ``_should_assign_at_confirm`` (``odoo19c: :1967-1968``)."""
        if self._should_bypass_reservation():
            return True
        if self.picking_type_id and self.picking_type.reservation_method == 'at_confirm':
            return True
        return bool(self.reservation_date
                    and self.reservation_date <= timezone.now().date())

    def _should_be_assigned(self):
        """≙ ``_should_be_assigned`` (``odoo19c: :1679-1681``).

        Un movimiento sin albarán pero con tipo de operación es candidato a
        que se le asigne uno.
        """
        return bool(self.picking_id is None and self.picking_type_id)

    def _can_create_lot(self):
        """≙ ``_can_create_lot`` (``odoo19c: :1046-1047``)."""
        return bool(self.picking_type_id and self.picking_type.use_existing_lots)

    def _skip_push(self):
        """≙ ``_skip_push`` (``odoo19c: :2226-2232``).

        No se aplica regla de empuje a un ajuste de inventario, ni cuando ya
        hay un destino encadenado cuya ubicación solapa con la nuestra: empujar
        ahí duplicaría el tramo.
        """
        if self.is_inventory:
            return True
        destinos = list(self.move_dest_ids.all())
        if not destinos:
            return False
        return any(
            m.location.is_child_of(self.location_dest)
            or self.location_dest.is_child_of(m.location)
            for m in destinos if m.location_id and self.location_dest_id
        )

    def _check_quantity(self):
        """≙ ``_check_quantity`` (``odoo19c: :2234-2239``).

        Delega en el quant: reúne los de este producto bajo la ubicación
        destino y su lote, y le pide la verificación.
        """
        Quant = apps.get_model('stock', 'StockQuant')
        quants = Quant.objects.filter(
            product=self.product,
            location__in=self.location_dest.child_ids_recursive()
            if self.location_dest_id else [],
        )
        return Quant.check_quantity(quants)

    def _get_picked_quantity(self):
        """≙ ``_get_picked_quantity`` (``odoo19c: :1970-1980``).

        Cuando el movimiento está marcado como recogido pero **alguna** de sus
        líneas no lo está, la cantidad recogida es la suma sólo de las que sí
        —no ``quantity``, que incluiría las no recogidas—.
        """
        lineas = list(self.move_line_ids.all())
        if self.picked and any(not ml.picked for ml in lineas):
            recogida = Decimal('0')
            for ml in lineas:
                if not ml.picked:
                    continue
                recogida += ml.product_uom._compute_quantity(
                    ml.quantity, self.product_uom, round=False)
            return recogida
        return self.quantity

    def _get_available_quantity(self, location, lot=None, package=None,
                                owner=None, strict=False, allow_negative=False):
        """≙ ``_get_available_quantity`` (``odoo19c: :1983-1987``).

        Si la ubicación se salta la reserva, todo está disponible por
        definición; en otro caso decide el quant.
        """
        if location is not None and location.should_bypass_reservation():
            return self.product_qty
        return StockQuant._get_available_quantity(
            self.product, location, lot=lot, package=package, owner=owner,
            strict=strict, allow_negative=allow_negative)

    def _get_lang(self):
        """≙ ``_get_lang`` (``odoo19c: :2439-2441``).

        El idioma de la descripción traducida: el del contacto del albarán, el
        del contacto del movimiento, o el del usuario.
        """
        if self.picking_id and self.picking.partner_id:
            if self.picking.partner.lang:
                return self.picking.partner.lang
        if self.partner_id and self.partner.lang:
            return self.partner.lang
        usuario = get_current_user()
        return getattr(usuario, 'lang', None)

    def _get_source_document(self):
        """≙ ``_get_source_document`` (``odoo19c: :2443-2448``).

        El documento del movimiento. La fuente declara el método como punto de
        extensión para que otros addons añadan su tipo de documento.
        """
        return self.picking if self.picking_id else None

    def _get_report_description_picking(self):
        """≙ ``_get_report_description_picking`` (``odoo19c: :2461-2466``).

        La descripción para el reporte, sin repetir el nombre del producto al
        principio — en el reporte el producto ya está en su propia columna.
        """
        descripcion = self.description_picking or ''
        nombre = str(self.product) if self.product_id else ''
        if nombre and descripcion.startswith(nombre):
            descripcion = descripcion[len(nombre):].strip()
        return descripcion

    def _get_partner_id(self):
        """≙ ``_get_partner_id`` (``odoo19c: :1818-1822``)."""
        if self.picking_id and self.picking.partner_id:
            return self.picking.partner
        return self.partner if self.partner_id else None

    def _get_mto_procurement_date(self):
        """≙ ``_get_mto_procurement_date`` (``odoo19c: :1864-1865``)."""
        return self.date

    def _prepare_procurement_origin(self):
        """≙ ``_prepare_procurement_origin`` (``odoo19c: :1780-1782``)."""
        return self.origin or (self.picking.name if self.picking_id else '')

    def _get_formating_options(self):
        """≙ ``_get_formating_options`` (``odoo19c: :1648-1649``).

        El nombre con la errata está **en la referencia** (``formating``, con
        una sola ``t``). Se conserva: renombrarlo rompería la correspondencia
        símbolo a símbolo por una mejora cosmética.
        """
        return {}

    def _key_assign_picking(self):
        """≙ ``_key_assign_picking`` (``odoo19c: :1522-1527``).

        La clave por la que dos movimientos comparten albarán. El albarán de
        los movimientos origen entra en la clave **sólo** si el movimiento no
        trae referencias propias: con referencia, ésta manda.
        """
        clave = (tuple(self.reference_ids.values_list('pk', flat=True)),
                 self.location_id, self.location_dest_id, self.picking_type_id)
        if not self.reference_ids.exists():
            origen_pickings = tuple(sorted(
                self.move_orig_ids.exclude(picking__isnull=True)
                .values_list('picking', flat=True)))
            if origen_pickings:
                clave += (origen_pickings,)
        return clave

    def _prepare_merge_moves_distinct_fields(self):
        """≙ ``_prepare_merge_moves_distinct_fields`` (``odoo19c: :1276-1288``).

        Los campos que **impiden** fusionar dos movimientos: si difieren en
        alguno, son movimientos distintos.
        """
        return [
            'product', 'price_unit', 'procure_method', 'location', 'location_dest',
            'location_final', 'product_uom', 'restrict_partner', 'scrapped',
            'origin_returned_move', 'package_level', 'propagate_cancel',
            'description_picking', 'date_deadline',
        ]

    def _prepare_merge_negative_moves_excluded_distinct_fields(self):
        """≙ ``_prepare_merge_negative_moves_excluded_distinct_fields``
        (``odoo19c: :1291-1292``).

        De la lista de arriba, el único campo que **no** cuenta al fusionar un
        movimiento negativo con su positivo.
        """
        return ['description_picking']

    def _clean_merged(self):
        """≙ ``_clean_merged`` (``odoo19c: :1294-1296``)."""
        self.move_ids_to_clean().update(propagate_cancel=False)

    def move_ids_to_clean(self):
        """El conjunto sobre el que ``_clean_merged`` escribe.

        Divergencia de mecanismo: la fuente llama ``self.write(...)`` sobre el
        recordset; aquí un modelo suelto no es un conjunto, así que el hogar de
        esa distinción es explícito. Sobre una instancia devuelve su propio
        queryset de un elemento.
        """
        return type(self).objects.filter(pk=self.pk)

    def _update_candidate_moves_list(self, candidate_moves_set):
        """≙ ``_update_candidate_moves_list`` (``odoo19c: :1298-1300``).

        Añade al conjunto de candidatos todos los movimientos de cada albarán
        implicado — la fusión mira el albarán entero, no sólo el movimiento.
        """
        if self.picking_id:
            candidate_moves_set.add(self.picking_id)
        return candidate_moves_set

    def _log_cancel_activity(self):
        """≙ ``_log_cancel_activity`` (``odoo19c: :2223-2225``).

        Vacío en la referencia: es el punto de extensión que otros addons
        sobreescriben para dejar la actividad al cancelar.
        """
        return

    def _action_synch_order(self):
        """≙ ``_action_synch_order`` (``odoo19c: :2311-2312``) — punto de extensión."""
        return True

    def _post_process_created_moves(self):
        """≙ ``_post_process_created_moves`` (``odoo19c: :2405-2409``).

        Punto de extensión de la referencia: acciones posteriores a la creación
        para movimientos que nunca se van a confirmar.
        """
        return None

    def _break_mto_link(self, parent_move):
        """≙ ``_break_mto_link`` (``odoo19c: :2786-2789``).

        Rompe el encadenamiento con el movimiento padre y devuelve este
        movimiento a fabricar-contra-existencias.
        """
        self.move_orig_ids.remove(parent_move)
        self.procure_method = self.PROCURE_MAKE_TO_STOCK
        self.save(update_fields=['procure_method', 'updated_at'])
        self._recompute_state()

    @staticmethod
    def _convert_string_into_field_data(string, options=None):
        """≙ ``_convert_string_into_field_data`` (``odoo19c: :2739-2743``).

        Interpreta lo escrito en el lector de código de barras: si es un
        número, es una cantidad. La coma se normaliza a punto porque
        ``float()`` sólo entiende el punto.
        """
        string = (string or '').replace(',', '.')
        if re.fullmatch(r'([0-9]+\.?[0-9]*|\.[0-9]+)', string):
            return {'quantity': float(string)}
        return False

    # -- ola B · persistencia: lo que pasa al crear, escribir y borrar --

    @classmethod
    def default_get(cls, field_names, values=None, default_picking=None):
        """≙ ``default_get`` (``odoo19c: :770-784``).

        El albarán de destino decide con qué estado nace el movimiento. La
        fuente lo lee del contexto (``default_picking_id``); aquí es un
        argumento explícito, igual que en ``stock_rule.default_get`` — este ORM
        no lleva contexto de entorno en la llamada.

        ``additional`` no es cosmético: es lo que hace que
        ``_autoconfirm_picking`` recoja el movimiento. Sin la marca, una línea
        añadida a un albarán ya en marcha se quedaría en borrador dentro de una
        transferencia que ya avanzó.
        """
        defaults = dict(values or {})
        if default_picking is None:
            return defaults
        if default_picking.state == 'done':
            defaults['state'] = cls.STATE_DONE
            defaults['additional'] = True
        elif default_picking.state not in ('cancel', 'draft', 'done'):
            defaults['additional'] = True    # dispara `_autoconfirm_picking`
        return defaults

    @staticmethod
    def _normalize_create_values(values):
        """≙ el bucle de normalización de ``create`` (``odoo19c: :819-826``).

        Se separa del ``create`` porque es la parte **pura**: sólo transforma
        el diccionario, sin tocar la base. Así se prueba sin insertar nada, y
        ``create`` queda con lo que sí es persistencia.

        Las tres reglas de la fuente, en su orden:

        1. Con cantidad (o con líneas), ``lot_ids`` sobra y se descarta —
           dejar ambos permitiría dos verdades sobre lo mismo.
        2. Un movimiento que nace dentro de un albarán hecho nace hecho.
        3. Todo movimiento hecho está recogido, por definición.
        """
        values = dict(values)
        if (values.get('quantity') or values.get('move_line_ids')) and 'lot_ids' in values:
            values.pop('lot_ids')
        albaran = values.get('picking')
        if albaran is not None and albaran.state == 'done' \
                and values.get('state') != StockMove.STATE_DONE:
            values['state'] = StockMove.STATE_DONE
        if values.get('state') == StockMove.STATE_DONE:
            values['picked'] = True
        return values

    @classmethod
    def create(cls, **vals):
        """≙ ``create`` (``odoo19c: :818-830``).

        Normaliza, inserta, y **luego** propaga: las reglas de reabastecimiento
        que este producto toca quedan marcadas para recalcularse, y el
        movimiento hereda las referencias de su albarán.
        """
        move = cls.objects.create(**cls._normalize_create_values(vals))
        move._update_orderpoints()
        move._set_references()
        return move

    def write(self, vals, skip_uom_conversion=False):
        """≙ ``write`` (``odoo19c: :833-905``) — la mitad de guardas.

        Dos prohibiciones de la fuente, con su razón:

        - **Cantidad de un cancelado.** El cancelado es un hecho histórico;
          reescribirlo borraría por qué se canceló. La fuente pide una línea
          nueva en su lugar.
        - **Unidad de un hecho.** Cambiarla reinterpreta una cantidad ya
          asentada: cinco cajas pasarían a ser cinco piezas sin que ningún
          quant se mueva. ``skip_uom_conversion`` es la puerta que la fuente
          deja abierta para quien sí sabe lo que hace.

        Divergencia declarada — **la mitad de reserva no está aquí.** La fuente
        encadena, tras las guardas, el des-reservar/re-asignar de
        ``product_uom_qty`` (``:851-871``), el aviso de fecha límite
        (``:872-873``) y el re-cálculo de almacén (``:891-899``). Esos cuelgan
        de ``_do_unreserve`` y ``_action_assign``, que son la **ola C**; se
        portan ahí y no antes, para no dejar medio mecanismo en pie. Cobertura
        declarada en el docstring del módulo.
        """
        for campo, valor in vals.items():
            if campo == 'quantity' and self.state == self.STATE_CANCEL:
                raise UserError(_(
                    'No puede cambiar un movimiento cancelado; cree una línea nueva.'))
            if (campo == 'product_uom' and self.state == self.STATE_DONE
                    and not skip_uom_conversion):
                raise UserError(_(
                    "No puede cambiar la unidad de un movimiento en estado 'Hecho'."))
            setattr(self, campo, valor)
        if {'product', 'location', 'location_dest'} & set(vals):
            self._update_orderpoints()
        self.save()
        if {'product', 'state', 'date', 'product_uom_qty',
                'location', 'location_dest'} & set(vals):
            self._update_orderpoints()
        if 'picking' in vals:
            self._set_references()
        return True

    def unlink(self, *args, **kwargs):
        """≙ ``unlink`` (``odoo19c: :2337-2343``).

        El orden importa y es el de la fuente: primero las líneas, después la
        fila. Y antes de todo, la guarda de cadena — que la fuente declara
        aparte, con ``@api.ondelete``, y aquí se invoca explícitamente porque
        este ORM no tiene ese decorador.

        Las reglas de reabastecimiento se capturan **antes** de borrar: después
        el movimiento ya no está para decir a cuáles tocaba.
        """
        self._unlink_if_draft_or_cancel()
        self.move_line_ids.all().delete()
        reglas = list(self._get_orderpoints_to_update())
        resultado = super().delete(*args, **kwargs)
        type(self)._mark_orderpoints_for_recompute(reglas)
        return resultado

    delete = unlink   # el nombre de Django apunta al de la referencia

    def _set_references(self):
        """≙ ``_set_references`` (``odoo19c: :793-796``).

        Un movimiento sin referencias propias adopta las de su albarán: es lo
        que hace que los documentos de un mismo encargo compartan nombre.
        """
        if not self.reference_ids.exists() and self.picking_id:
            self.reference_ids.set(self.picking.reference_ids)

    @property
    def display_name(self):
        """≙ ``display_name`` / ``_compute_display_name`` (``odoo19c: :786-792``).

        ``origen/código: ubicación>destino``, con los dos primeros tramos
        opcionales — la fuente los omite cuando están vacíos en vez de dejar
        separadores huérfanos.
        """
        origen = self.picking.origin if self.picking_id else ''
        codigo = self.product.code_for(None) if self.product_id else ''
        return '%s%s%s>%s' % (
            f'{origen}/' if origen else '',
            f'{codigo}: ' if codigo else '',
            self.location.name if self.location_id else '',
            self.location_dest.name if self.location_dest_id else '')

    # -- ola B · propagación a las reglas de reabastecimiento --

    def _update_orderpoints(self):
        """≙ ``_update_orderpoints`` (``odoo19c: :908-916``).

        Marca para recálculo **sólo** las reglas del almacén afectado, no todas
        las del producto. La fuente lo dice explícito: *"instead of all the
        orderpoints linked to the product"*.
        """
        if self.pk is None:
            return
        type(self)._mark_orderpoints_for_recompute(self._get_orderpoints_to_update())

    def _get_orderpoints_to_update(self):
        """≙ ``_get_orderpoints_to_update`` (``odoo19c: :918-927``).

        Las reglas de este producto, acotadas a los almacenes que el movimiento
        toca — origen y destino. Sin almacén en ninguno de los dos extremos, el
        acotamiento no aplica y quedan todas las del producto.
        """
        orderpoint = apps.get_model('stock', 'StockWarehouseOrderpoint')
        if self.product_id is None:
            return orderpoint.objects.none()
        almacenes = [
            a for a in (
                self.location.warehouse_id if self.location_id else None,
                self.location_dest.warehouse_id if self.location_dest_id else None,
            ) if a is not None
        ]
        reglas = orderpoint.objects.filter(product_id=self.product_id)
        if almacenes:
            reglas = reglas.filter(warehouse_id__in=almacenes)
        return reglas.order_by('id')

    @classmethod
    def _mark_orderpoints_for_recompute(cls, orderpoints):
        """El ``add_to_compute`` de la fuente (``odoo19c: :916``), explícito.

        Divergencia declarada: allá el ORM difiere el cálculo hasta la próxima
        lectura del campo. Este ORM no tiene cola de cómputo diferido —
        construirla es la tarea **#191**— así que el recálculo se ejecuta ya.
        Es la misma cifra; cambia cuándo se paga.
        """
        reglas = list(orderpoints)
        if reglas:
            type(reglas[0])._compute_qty_to_order_computed(reglas)

    # -- ola B · el aviso de retraso --

    def _delay_alert_get_documents(self):
        """≙ ``_delay_alert_get_documents`` (``odoo19c: :929-938``).

        Los documentos sobre los que se publica el aviso de retraso. La fuente
        lo declara para que otros módulos lo extiendan añadiendo su propio tipo
        de documento (la orden de compra, la de fabricación); aquí sólo está el
        albarán, que es lo que ``stock`` conoce.
        """
        return [self.picking] if self.picking_id else []

    def _propagate_date_log_note(self, move_orig):
        """≙ ``_propagate_date_log_note`` (``odoo19c: :940-957``).

        Publica en los documentos de este movimiento que su fecha límite se
        movió por un retraso aguas arriba. La guarda contra el duplicado es de
        la fuente: si el último mensaje ya dice lo mismo, no se repite.
        """
        docs_origen = move_orig._delay_alert_get_documents()
        documentos = self._delay_alert_get_documents()
        if not documentos or not docs_origen:
            return
        cuerpo = _('La fecha límite se actualizó por un retraso en %s.') % docs_origen[0]
        asunto = _('Fecha límite actualizada por retraso en %s') % docs_origen[0]
        for doc in documentos:
            ultimo = doc.message_ids.order_by('-id').first()
            if ultimo is not None and ultimo.subject == asunto:
                continue
            doc.message_post(body=cuerpo, subject=asunto)

    def _unlink_if_draft_or_cancel(self):
        """≙ ``_unlink_if_draft_or_cancel`` (``odoo19c: :2333-2335``).

        Un movimiento encadenado sólo se borra si está en borrador o
        cancelado: borrar uno intermedio dejaría la cadena rota.
        """
        if self.state not in (self.STATE_DRAFT, self.STATE_CANCEL) and (
                self.move_orig_ids.exists() or self.move_dest_ids.exists()):
            raise UserError(_('No puede eliminar movimientos enlazados a otra operación'))

    def _get_relevant_state_among_moves(self, moves=None):
        """≙ ``_get_relevant_state_among_moves`` (``odoo19c: :1406-1446``).

        El estado que representa a un conjunto de movimientos — lo consume el
        albarán para derivar el suyo. El orden de importancia lo fija la
        referencia: asignado > esperando > parcial > confirmado.

        Con política «todo junto» (``move_type == 'one'``) manda el movimiento
        **más** importante, porque basta uno sin resolver para frenar el envío
        completo; con «lo antes posible» manda el **menos** importante, porque
        cualquiera resuelto ya permite enviar.
        """
        orden = {'assigned': 4, 'waiting': 3, 'partially_available': 2, 'confirmed': 1}
        candidatos = [
            m for m in (moves if moves is not None else [self])
            if m.state not in (self.STATE_CANCEL, self.STATE_DONE)
            and not (m.state == self.STATE_ASSIGNED and not m.product_uom_qty)
        ]
        if not candidatos:
            return self.STATE_ASSIGNED
        candidatos.sort(key=lambda m: (orden.get(m.state, 0), m.product_uom_qty))
        primero = candidatos[0]
        albaran = primero.picking if primero.picking_id else None
        if albaran is not None and albaran.move_type == 'one':
            if all(not m.product_uom_qty for m in candidatos):
                return self.STATE_ASSIGNED
            if primero.state in (self.STATE_CONFIRMED, 'partially_available'):
                return self.STATE_CONFIRMED
            return primero.state or self.STATE_DRAFT
        if primero.state != self.STATE_ASSIGNED and any(
                m.state in (self.STATE_ASSIGNED, 'partially_available')
                for m in candidatos):
            return 'partially_available'
        ultimo = candidatos[-1]
        if ultimo.state == self.STATE_CONFIRMED and not ultimo.product_uom_qty:
            return self.STATE_ASSIGNED
        return ultimo.state or self.STATE_DRAFT

    def _recompute_state(self):
        """≙ ``_recompute_state`` (``odoo19c: :2411-2431``).

        Deriva el estado de la relación entre lo reservado y lo pedido. El
        contexto ``preserve_state`` de la fuente es un parámetro explícito
        aquí: este ORM no lleva contexto de entorno en la llamada.
        """
        if self.state in (self.STATE_CANCEL, self.STATE_DONE):
            return
        if self.state == self.STATE_DRAFT and not self.quantity:
            return
        redondeo = self.product_uom.rounding if self.product_uom_id else Decimal('0.01')
        if float_compare(self.quantity, self.product_uom_qty,
                         precision_rounding=redondeo) >= 0:
            nuevo = self.STATE_ASSIGNED
        elif self.quantity and float_compare(
                self.quantity, self.product_uom_qty,
                precision_rounding=redondeo) <= 0:
            nuevo = 'partially_available'
        elif (self.procure_method == self.PROCURE_MAKE_TO_ORDER
              and not self.move_orig_ids.exists()) or any(
                orig.product_uom_qty > 0
                and orig.state not in (self.STATE_DONE, self.STATE_CANCEL)
                for orig in self.move_orig_ids.all()):
            nuevo = self.STATE_WAITING
        else:
            nuevo = self.STATE_CONFIRMED
        if self.state != nuevo:
            self.state = nuevo
            self.save(update_fields=['state', 'updated_at'])

    # -- el recorrido de la cadena de movimientos --

    def _rollup_moves(self, origin=True, seen=None):
        """≙ ``_rollup_moves`` (``odoo19c: :2674-2688``).

        Recorre la cadena en la dirección pedida y devuelve **los ids** de todo
        lo visitado. ``seen`` corta el ciclo: una cadena puede volver sobre sí
        misma y sin el acumulador el recorrido no termina.

        Divergencia declarada: la fuente devuelve ``OrderedSet``, que este
        árbol aún no tiene (tarea **#357**). Aquí un ``dict`` vacío hace de
        conjunto ordenado — Python garantiza el orden de inserción desde 3.7,
        que es exactamente la propiedad que ``OrderedSet`` aporta.
        """
        campo = 'move_orig_ids' if origin else 'move_dest_ids'
        if seen is None:
            seen = {}
        if self.pk in seen:
            return seen
        seen[self.pk] = None
        for siguiente in getattr(self, campo).all():
            siguiente._rollup_moves(origin, seen)
        return seen

    def _rollup_move_dests(self, seen=None):
        """≙ ``_rollup_move_dests`` (``odoo19c: :2668-2669``)."""
        return self._rollup_moves(origin=False, seen=seen)

    def _rollup_move_origs(self, seen=None):
        """≙ ``_rollup_move_origs`` (``odoo19c: :2671-2672``)."""
        return self._rollup_moves(origin=True, seen=seen)

    def _rollup_move_dests_fetch(self):
        """≙ ``_rollup_move_dests_fetch`` (``odoo19c: :2648-2656``).

        En la referencia precarga la cadena para no pagar una consulta por
        salto. Aquí el equivalente es materializar el recorrido: el ORM de
        Django no tiene ``fetch()`` de campo suelto, y ``prefetch_related``
        no atraviesa profundidad arbitraria.
        """
        return list(self._rollup_move_dests())

    def _rollup_move_origs_fetch(self):
        """≙ ``_rollup_move_origs_fetch`` (``odoo19c: :2658-2666``)."""
        return list(self._rollup_move_origs())

    def _get_upstream_documents_and_responsibles(self, visited=None):
        """≙ ``_get_upstream_documents_and_responsibles`` (``odoo19c: :2450-2459``).

        Asciende por la cadena hasta el documento vivo más alto y devuelve los
        pares (documento, responsable). Un movimiento sin origen vivo es la
        cima: ahí la fuente devuelve lista vacía y el descendiente decide.
        """
        if visited is None:
            visited = set()
        if self.pk in visited:
            return set()
        origenes = [m for m in self.move_orig_ids.all()
                    if m.state not in (self.STATE_DONE, self.STATE_CANCEL)]
        if not origenes:
            return set()
        visited.add(self.pk)
        salida = set()
        for movimiento in origenes:
            salida |= movimiento._get_upstream_documents_and_responsibles(visited)
        return salida

    def _do_unreserve(self):
        """≙ ``_do_unreserve`` (``odoo19c: :1018-1044``).

        Suelta la reserva borrando las líneas no recogidas. Tres casos que la
        fuente salta en silencio y aquí también: cancelado, hecho hacia
        inventario (un desecho), y ya recogido.

        Un movimiento **hecho** sí revienta: soltar la reserva de algo ya
        entregado no tiene sentido y la fuente lo declara error.
        """
        if self.state == self.STATE_CANCEL:
            return True
        if self.state == self.STATE_DONE:
            if self.location_dest_usage == 'inventory':
                return True
            raise UserError(
                _('No puede quitar la reserva de un movimiento ya hecho.'))
        if self.picked:
            return True
        lineas = list(self.move_line_ids.all())
        recogida_alguna = any(ml.picked for ml in lineas)
        for ml in lineas:
            if not ml.picked:
                ml.delete()
        # ``write`` sobre la línea no dispara ``_recompute_state`` (a diferencia
        # de ``unlink``), así que hay que llamarlo donde no se borró ninguna.
        if recogida_alguna:
            self._recompute_state()
        return True

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
