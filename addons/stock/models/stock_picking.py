"""``stock.picking.type`` y ``stock.picking`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_picking.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el **tipo de operación** es la plantilla que gobierna una clase de
transferencia —recepción, entrega, movimiento interno— y decide su secuencia de
referencia, sus ubicaciones por defecto, su política de reserva y qué se imprime
al validar. La **transferencia** (albarán) es la instancia: un lote de
movimientos que va de una ubicación a otra bajo ese tipo.

Porte símbolo por símbolo — ``StockPickingType``
=================================================

Medido sobre ``odoo19c: addons/stock/models/stock_picking.py:20-537``:
**49 campos + 34 métodos = 83 símbolos**. Todos portados.

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``name`` (27)                                    ``name``
``color`` (28)                                   ``color``
``sequence`` (29)                                ``sequence``
``sequence_id`` (30-32)                          ``sequence_id`` (colisión, ver D-1)
``sequence_code`` (33)                           ``sequence_code``
``default_location_src_id`` (34-37)              ``default_location_src`` (almacenado)
``default_location_dest_id`` (38-41)             ``default_location_dest`` (almacenado)
``code`` (42)                                    ``code``
``return_picking_type_id`` (43-46)               ``return_picking_type``
``show_entire_packs`` (47)                       ``show_entire_packs``
``set_package_type`` (48)                        ``set_package_type``
``warehouse_id`` (49-51)                         ``warehouse`` (almacenado)
``active`` (52)                                  ``active``
``use_create_lots`` (53-56)                      ``use_create_lots`` (almacenado)
``use_existing_lots`` (57-60)                    ``use_existing_lots`` (almacenado)
``print_label`` (61-63)                          ``print_label`` (almacenado)
``show_operations`` (65-67)                      ``show_operations``
``reservation_method`` (68-71)                   ``reservation_method``
``reservation_days_before`` (72)                 ``reservation_days_before``
``reservation_days_before_priority`` (73)        ``reservation_days_before_priority``
``auto_show_reception_report`` (74-76)           ``auto_show_reception_report``
``auto_print_delivery_slip`` (77-79)             ``auto_print_delivery_slip``
``auto_print_return_slip`` (80-82)               ``auto_print_return_slip``
``auto_print_product_labels`` (84-86)            ``auto_print_product_labels``
``product_label_format`` (87-95)                 ``product_label_format``
``auto_print_lot_labels`` (96-98)                ``auto_print_lot_labels``
``lot_label_format`` (99-104)                    ``lot_label_format``
``auto_print_reception_report`` (105-107)        ``auto_print_reception_report``
``auto_print_reception_report_labels`` (108-110) ``auto_print_reception_report_labels``
``auto_print_packages`` (111-113)                ``auto_print_packages``
``auto_print_package_label`` (115-117)           ``auto_print_package_label``
``package_label_to_print`` (118-120)             ``package_label_to_print``
``count_picking_draft`` (122)                    property ``count_picking_draft``
``count_picking_ready`` (123)                    property ``count_picking_ready``
``count_picking`` (124)                          property ``count_picking``
``count_picking_waiting`` (125)                  property ``count_picking_waiting``
``count_picking_late`` (126)                     property ``count_picking_late``
``count_picking_backorders`` (127)               property ``count_picking_backorders``
``count_move_ready`` (128)                       property ``count_move_ready``
``hide_reservation_method`` (129)                property ``hide_reservation_method``
``barcode`` (130)                                ``barcode``
``company_id`` (131-133)                         ``company``
``create_backorder`` (134-140)                   ``create_backorder``
``show_picking_type`` (141)                      property ``show_picking_type``
``picking_properties_definition`` (143)          ``picking_properties_definition``
``favorite_user_ids`` (144-146)                  ``favorite_user_ids`` (M2M + through)
``is_favorite`` (147-150)                        property ``is_favorite``
``kanban_dashboard_graph`` (151)                 property ``kanban_dashboard_graph``
``move_type`` (152-155)                          ``move_type``
``create`` (157-173)                             ``create`` (classmethod)
``copy_data`` (175-183)                          ``copy_data``
``write`` (185-219)                              ``write``
``_search_is_favorite`` (221-225)                ``search_is_favorite`` (classmethod)
``_compute_is_favorite`` (227-229)               property ``is_favorite``
``_inverse_is_favorite`` (231-237)               ``set_is_favorite``
``_order_field_to_sql`` (239-247)                ``order_by_favorite`` (classmethod)
``_compute_hide_reservation_method`` (249-252)   property ``hide_reservation_method``
``_compute_picking_count`` (254-270)             ``get_picking_count`` + 6 properties
``_compute_move_count`` (272-279)                property ``count_move_ready``
``_compute_display_name`` (281-288)              ``__str__``
``_compute_use_create_lots`` (290-294)           ``compute_use_create_lots``
``_compute_use_existing_lots`` (296-300)         ``compute_use_existing_lots``
``_search_display_name`` (302-314)               ``search_display_name`` (classmethod)
``_compute_default_location_src_id`` (316-325)   ``compute_default_location_src``
``_compute_default_location_dest_id`` (327-336)  ``compute_default_location_dest``
``_compute_print_label`` (338-344)               ``compute_print_label``
``_onchange_picking_code`` (346-353)             ``check_picking_code_warning``
``_compute_warehouse_id`` (355-363)              ``compute_warehouse``
``_compute_show_picking_type`` (365-368)         property ``show_picking_type``
``_compute_kanban_dashboard_graph`` (370-392)    property ``kanban_dashboard_graph``
``_onchange_sequence_code`` (394-406)            ``check_sequence_code_warning``
``action_redirect_to_barcode_installation`` (408-412) ``action_redirect_to_barcode_installation``
``_get_action`` (414-441)                        ``get_action``
``get_action_picking_tree_late`` (443-444)       ``get_action_picking_tree_late``
``get_action_picking_tree_backorder`` (446-447)  ``get_action_picking_tree_backorder``
``get_action_picking_tree_waiting`` (449-450)    ``get_action_picking_tree_waiting``
``get_action_picking_tree_ready`` (452-453)      ``get_action_picking_tree_ready``
``get_action_picking_type_moves_analysis`` (455-460) ``get_action_picking_type_moves_analysis``
``get_stock_picking_action_picking_type`` (462-470) ``get_stock_picking_action_picking_type``
``get_action_picking_type_ready_moves`` (472-473) ``get_action_picking_type_ready_moves``
``_get_aggregated_records_by_date`` (475-492)    ``get_aggregated_records_by_date``
``_prepare_graph_data`` (494-525)                ``prepare_graph_data``
``_get_code_report_name`` (527-535)              ``get_code_report_name``
===============================================  ======================================

Divergencias declaradas
=========================

**D-1 · ``sequence_id`` conserva el sufijo.** La convención de este árbol quita
el ``_id`` de un Many2one (``warehouse_id`` → ``warehouse``), pero aquí
colisionaría con ``sequence``, que es el ``Integer`` de orden. Se conserva el
nombre **de la referencia** en vez de inventar uno: es la opción que menos
diverge de la fuente.

**D-2 · Los ``compute`` sin ``store`` son ``property``.** Los seis
``count_picking*``, ``count_move_ready``, ``hide_reservation_method``,
``show_picking_type``, ``is_favorite`` y ``kanban_dashboard_graph`` no tienen
columna allá y no la tienen aquí. Los cinco que **sí** almacena
(``default_location_src``, ``default_location_dest``, ``warehouse``,
``use_create_lots``, ``use_existing_lots``, ``print_label``) son columnas, y su
recálculo se dispara en ``save()``.

**D-3 · ``_order`` por ``is_favorite`` es un método, no ``Meta.ordering``.**
La referencia ordena por un campo calculado y para eso sobreescribe
``_order_field_to_sql``, que emite ``id IN (SELECT picking_type_id FROM
picking_type_favorite_user_rel WHERE user_id = %s)``. Django no ordena por una
``property``; el mismo SQL se obtiene con ``Exists`` sobre la tabla de
relación, así que el mecanismo vive en ``order_by_favorite(queryset, user)`` y
``Meta.ordering`` conserva el resto del criterio (``sequence, id``).

**D-4 · Los ``@api.onchange`` son métodos explícitos.**
``check_picking_code_warning`` y ``check_sequence_code_warning`` devuelven el
mismo aviso que la referencia; lo que se pierde es el disparo automático en un
formulario que este stack no tiene.

**D-5 · Las acciones de ventana devuelven el descriptor, no lo resuelven.**
``get_action`` reproduce la forma de ``_get_action`` (contexto, dominio, nombre
visible) leyendo ``IrActionsActWindow`` por identificador externo. El
``_render_template`` de ``stock.help_message_template`` exige el renderizador
QWeb, que es la tarea **#273**: hasta entonces ``help`` queda en cadena vacía y
la clave se conserva para no cambiar la forma del descriptor.
"""
import json
import datetime
import uuid

import fields
import models
from django.apps import apps
from django.db.models import Exists, OuterRef, Q

from addons.base.models import TimeStampedModel
from addons.base.models.res_users import ResUsers
from exceptions import UserError
from tools.translate import _

CODE_INCOMING = 'incoming'
CODE_OUTGOING = 'outgoing'
CODE_INTERNAL = 'internal'

#: ≙ ``code`` (``odoo19c: :42``).
CODE_CHOICES = [
    (CODE_INCOMING, 'Recepción'),
    (CODE_OUTGOING, 'Entrega'),
    (CODE_INTERNAL, 'Transferencia interna'),
]

#: ≙ ``reservation_method`` (``:68-71``).
RESERVATION_METHOD_CHOICES = [
    ('at_confirm', 'Al confirmar'),
    ('manual', 'Manualmente'),
    ('by_date', 'Antes de la fecha prevista'),
]

#: ≙ ``product_label_format`` (``:87-95``).
PRODUCT_LABEL_FORMAT_CHOICES = [
    ('dymo', 'Dymo'),
    ('2x7xprice', '2 × 7 con precio'),
    ('4x7xprice', '4 × 7 con precio'),
    ('4x12', '4 × 12'),
    ('4x12xprice', '4 × 12 con precio'),
    ('zpl', 'Etiquetas ZPL'),
    ('zplxprice', 'Etiquetas ZPL con precio'),
]

#: ≙ ``lot_label_format`` (``:99-104``).
LOT_LABEL_FORMAT_CHOICES = [
    ('4x12_lots', '4 × 12 — una por lote/serie'),
    ('4x12_units', '4 × 12 — una por unidad'),
    ('zpl_lots', 'Etiquetas ZPL — una por lote/serie'),
    ('zpl_units', 'Etiquetas ZPL — una por unidad'),
]

#: ≙ ``package_label_to_print`` (``:118-120``).
PACKAGE_LABEL_CHOICES = [('pdf', 'PDF'), ('zpl', 'ZPL')]

#: ≙ ``create_backorder`` (``:134-140``).
CREATE_BACKORDER_CHOICES = [
    ('ask', 'Preguntar'),
    ('always', 'Siempre'),
    ('never', 'Nunca'),
]

#: ≙ ``move_type`` (``:152-155``).
MOVE_TYPE_CHOICES = [
    ('direct', 'En cuanto sea posible'),
    ('one', 'Cuando todos los productos estén listos'),
]

#: ≙ los identificadores externos que ``_compute_default_location_*`` resuelve.
XMLID_LOCATION_SUPPLIERS = 'stock.stock_location_suppliers'
XMLID_LOCATION_CUSTOMERS = 'stock.stock_location_customers'


class StockPickingType(TimeStampedModel):
    """``stock.picking.type`` — la plantilla que gobierna una clase de albarán."""

    _name = 'stock.picking.type'
    _description = "Picking Type"

    name                     = fields.Char(
        'Operation Type', max_length=100, required=True, translate=True,
        help='Nombre del tipo de operación (Odoo name).',
    )
    color                    = fields.Integer(
        default=0, help_text='Color del kanban (Odoo color).',
    )
    sequence                 = fields.Integer(
        default=0,
        help_text='Orden en la vista «Todas las operaciones» (Odoo sequence).',
    )
    # D-1: se conserva el sufijo ``_id`` porque ``sequence`` ya es el Integer.
    sequence_id              = fields.Many2one(
        'base.IrSequence', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='picking_types',
        help_text='Secuencia de referencia (Odoo sequence_id).',
    )
    sequence_code            = fields.Char(
        'Sequence Prefix', max_length=32, required=True,
        help='Prefijo de la secuencia (Odoo sequence_code).',
    )
    default_location_src     = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.PROTECT,
        related_name='picking_types_src',
        help_text='Ubicación de origen por defecto '
                  '(Odoo default_location_src_id, almacenado).',
    )
    default_location_dest    = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.PROTECT,
        related_name='picking_types_dest',
        help_text='Ubicación de destino por defecto '
                  '(Odoo default_location_dest_id, almacenado).',
    )
    code                     = fields.Selection(
        max_length=16, choices=CODE_CHOICES, default=CODE_INCOMING,
        help_text='Tipo de operación (Odoo code, requerido).',
    )
    return_picking_type      = fields.Many2one(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='returned_by', db_index=True,
        help_text='Tipo de operación para devoluciones '
                  '(Odoo return_picking_type_id).',
    )
    show_entire_packs        = fields.Boolean(
        default=False,
        help_text='Mostrar paquetes completos en vez de su contenido '
                  '(Odoo show_entire_packs).',
    )
    set_package_type         = fields.Boolean(
        default=False,
        help_text='Permite elegir el tipo de paquete al empaquetar '
                  '(Odoo set_package_type).',
    )
    warehouse                = fields.Many2one(
        'stock.StockWarehouse', null=True, blank=True, on_delete=models.CASCADE,
        related_name='picking_type_ids',
        help_text='Almacén dueño del tipo (Odoo warehouse_id, almacenado).',
    )
    active                   = fields.Boolean(
        default=True,
        help_text='Al desmarcarlo se archiva sin borrar (Odoo active).',
    )
    use_create_lots          = fields.Boolean(
        default=True,
        help_text='Permite crear lotes/series nuevos '
                  '(Odoo use_create_lots, almacenado).',
    )
    use_existing_lots        = fields.Boolean(
        default=True,
        help_text='Permite elegir lotes/series existentes '
                  '(Odoo use_existing_lots, almacenado).',
    )
    print_label              = fields.Boolean(
        default=False,
        help_text='Genera etiqueta de envío al validar '
                  '(Odoo print_label, almacenado).',
    )
    # La referencia marca este campo para retirarlo («TODO: delete this field»,
    # ``odoo19c: :64``); se porta igual para no divergir antes que ella.
    show_operations          = fields.Boolean(
        default=False,
        help_text='Muestra las operaciones detalladas (Odoo show_operations).',
    )
    reservation_method       = fields.Selection(
        max_length=16, choices=RESERVATION_METHOD_CHOICES, default='at_confirm',
        help_text='Cuándo se reservan los productos (Odoo reservation_method).',
    )
    reservation_days_before  = fields.Integer(
        default=0,
        help_text='Días máximos antes de la fecha prevista para reservar '
                  '(Odoo reservation_days_before).',
    )
    reservation_days_before_priority = fields.Integer(
        default=0,
        help_text='Días máximos para reservar cuando la transferencia es '
                  'prioritaria (Odoo reservation_days_before_priority).',
    )
    auto_show_reception_report = fields.Boolean(
        default=False,
        help_text='Muestra el informe de recepción al validar '
                  '(Odoo auto_show_reception_report).',
    )
    auto_print_delivery_slip = fields.Boolean(
        default=False,
        help_text='Imprime el albarán de entrega al validar '
                  '(Odoo auto_print_delivery_slip).',
    )
    auto_print_return_slip   = fields.Boolean(
        default=False,
        help_text='Imprime el comprobante de devolución al validar '
                  '(Odoo auto_print_return_slip).',
    )
    auto_print_product_labels = fields.Boolean(
        default=False,
        help_text='Imprime las etiquetas de producto al validar '
                  '(Odoo auto_print_product_labels).',
    )
    product_label_format     = fields.Selection(
        max_length=16, choices=PRODUCT_LABEL_FORMAT_CHOICES, default='2x7xprice',
        help_text='Formato de etiqueta de producto (Odoo product_label_format).',
    )
    auto_print_lot_labels    = fields.Boolean(
        default=False,
        help_text='Imprime las etiquetas de lote/serie al validar '
                  '(Odoo auto_print_lot_labels).',
    )
    lot_label_format         = fields.Selection(
        max_length=16, choices=LOT_LABEL_FORMAT_CHOICES, default='4x12_lots',
        help_text='Formato de etiqueta de lote/serie (Odoo lot_label_format).',
    )
    auto_print_reception_report = fields.Boolean(
        default=False,
        help_text='Imprime el informe de recepción al validar '
                  '(Odoo auto_print_reception_report).',
    )
    auto_print_reception_report_labels = fields.Boolean(
        default=False,
        help_text='Imprime las etiquetas del informe de recepción al validar '
                  '(Odoo auto_print_reception_report_labels).',
    )
    auto_print_packages      = fields.Boolean(
        default=False,
        help_text='Imprime los paquetes y su contenido al validar '
                  '(Odoo auto_print_packages).',
    )
    auto_print_package_label = fields.Boolean(
        default=False,
        help_text='Imprime la etiqueta del paquete al empaquetar '
                  '(Odoo auto_print_package_label).',
    )
    package_label_to_print   = fields.Selection(
        max_length=8, choices=PACKAGE_LABEL_CHOICES, default='pdf',
        help_text='Formato de la etiqueta de paquete '
                  '(Odoo package_label_to_print).',
    )
    barcode                  = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Código de barras del tipo (Odoo barcode).',
    )
    company                  = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='picking_types', db_index=True,
        help_text='Empresa dueña del tipo (Odoo company_id, requerido).',
    )
    create_backorder         = fields.Selection(
        max_length=8, choices=CREATE_BACKORDER_CHOICES, default='ask',
        help_text='Qué hacer con lo que queda al validar '
                  '(Odoo create_backorder).',
    )
    picking_properties_definition = fields.PropertiesDefinition(
        'Picking Properties', default=dict, blank=True,
        help_text='Definición de propiedades de la transferencia '
                  '(Odoo picking_properties_definition).',
    )
    favorite_user_ids        = fields.Many2many(
        ResUsers, through='PickingTypeFavoriteUserRel',
        related_name='favorite_picking_types', blank=True,
        help_text='Usuarios que marcaron el tipo como favorito '
                  '(Odoo favorite_user_ids).',
    )
    move_type                = fields.Selection(
        max_length=8, choices=MOVE_TYPE_CHOICES, default='direct',
        help_text='Política de envío: parcial o todo junto (Odoo move_type).',
    )

    class Meta:
        db_table = 'stock_picking_type'
        # ≙ ``_order = 'is_favorite desc, sequence, id'`` — el tramo calculado
        # lo aporta ``order_by_favorite`` (D-3).
        ordering = ['sequence', 'id']
        verbose_name = 'Tipo de operación'
        verbose_name_plural = 'Tipos de operación'

    def __str__(self) -> str:
        """≙ ``_compute_display_name`` (``odoo19c: :281-288``).

        Con almacén, el nombre visible es ``<almacén>: <tipo>``.
        """
        if self.warehouse is not None:
            return f'{self.warehouse.name}: {self.name}'
        return self.name

    # -- creación, copia y escritura --

    @classmethod
    def create(cls, **vals):
        """≙ ``create`` (``odoo19c: :157-173``).

        Sin secuencia explícita pero con prefijo, se crea la ``ir.sequence``
        que le corresponde: con almacén el prefijo lleva su código delante
        (``WH/IN/``); sin él, el prefijo a secas.
        """
        ir_sequence = apps.get_model('base', 'IrSequence')
        if not vals.get('sequence_id') and vals.get('sequence_code'):
            warehouse = vals.get('warehouse')
            if warehouse is not None:
                vals['sequence_id'] = ir_sequence.objects.create(
                    name=_('Secuencia %(code)s de %(warehouse)s') % {
                        'code': vals['sequence_code'], 'warehouse': warehouse.name},
                    prefix=f"{warehouse.code}/{vals['sequence_code']}/",
                    padding=5,
                    company=warehouse.company,
                )
            else:
                vals['sequence_id'] = ir_sequence.objects.create(
                    name=_('Secuencia %(code)s') % {'code': vals['sequence_code']},
                    prefix=vals['sequence_code'],
                    padding=5,
                    company=vals.get('company'),
                )
        return cls.objects.create(**vals)

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: :175-183``).

        El nombre y el prefijo de la copia se marcan como tales; si el llamador
        ya fijó uno de los dos, ese gana.
        """
        default = dict(default or {})
        vals = {
            'name': default.get('name', _('%s (copia)') % self.name),
            'code': self.code,
            'company': self.company,
            'warehouse': self.warehouse,
        }
        if 'sequence_code' not in default and 'sequence_id' not in default:
            vals['sequence_code'] = _('%s (copia)') % self.sequence_code
        else:
            vals['sequence_code'] = default.get('sequence_code', self.sequence_code)
        return vals

    def write(self, vals):
        """≙ ``write`` (``odoo19c: :185-219``).

        Tres reglas de la referencia, en su orden:

        1. cambiar de empresa está prohibido — se archiva y se crea otro;
        2. cambiar el prefijo reescribe la ``ir.sequence`` asociada;
        3. cambiar el método de reserva recalcula (o borra) la fecha de reserva
           de los movimientos abiertos del tipo.
        """
        stock_move = apps.get_model('stock', 'StockMove')

        if 'company' in vals and self.company != vals['company']:
            raise UserError(_(
                'Cambiar la empresa de este registro está prohibido en este '
                'punto; archívelo y cree uno nuevo.'))

        if 'sequence_code' in vals and self.sequence_id is not None:
            if self.warehouse is not None:
                self.sequence_id.name = _('Secuencia %(code)s de %(warehouse)s') % {
                    'code': vals['sequence_code'], 'warehouse': self.warehouse.name}
                self.sequence_id.prefix = (
                    f"{self.warehouse.code}/{vals['sequence_code']}/")
                self.sequence_id.company = self.warehouse.company
            else:
                self.sequence_id.name = _('Secuencia %(code)s') % {
                    'code': vals['sequence_code']}
                self.sequence_id.prefix = vals['sequence_code']
            self.sequence_id.padding = 5
            self.sequence_id.save()

        if 'reservation_method' in vals:
            if vals['reservation_method'] == 'by_date':
                if self.reservation_method != 'by_date':
                    abiertos = stock_move.objects.filter(
                        picking_type=self,
                        state__in=('draft', 'confirmed', 'waiting',
                                   'partially_available'),
                    )
                    comunes = (vals.get('reservation_days_before')
                               or self.reservation_days_before)
                    prioritarios = (vals.get('reservation_days_before_priority')
                                    or self.reservation_days_before_priority)
                    for move in abiertos:
                        dias = prioritarios if move.priority == '1' else comunes
                        if move.date is not None:
                            move.reservation_date = (
                                move.date.date() - datetime.timedelta(days=dias))
                            move.save(update_fields=['reservation_date'])
            elif self.reservation_method == 'by_date':
                stock_move.objects.filter(
                    picking_type=self,
                ).exclude(
                    state__in=('assigned', 'done', 'cancel'),
                ).update(reservation_date=None)

        for nombre, valor in vals.items():
            setattr(self, nombre, valor)
        self.save()
        return self

    # -- favoritos --

    @classmethod
    def search_is_favorite(cls, user):
        """≙ ``_search_is_favorite`` (``odoo19c: :221-225``)."""
        return cls.objects.filter(favorite_user_ids=user)

    @property
    def is_favorite(self):
        """≙ ``_compute_is_favorite`` (``odoo19c: :227-229``).

        La referencia lo evalúa contra ``self.env.user``; aquí no hay usuario
        implícito, así que la property responde por el conjunto y el caso
        per-usuario lo cubre :meth:`is_favorite_of`.
        """
        return self.favorite_user_ids.exists()

    def is_favorite_of(self, user):
        """El predicado per-usuario que la referencia obtiene de ``env.user``."""
        return self.favorite_user_ids.filter(pk=user.pk).exists()

    def set_is_favorite(self, user, valor=None):
        """≙ ``_inverse_is_favorite`` (``odoo19c: :231-237``).

        Sin ``valor`` conmuta, que es lo que hace la referencia: lo que no
        estaba favorito pasa a estarlo, y lo que estaba deja de estarlo.
        """
        estaba = self.is_favorite_of(user)
        nuevo = (not estaba) if valor is None else bool(valor)
        if nuevo and not estaba:
            self.favorite_user_ids.add(user)
        elif not nuevo and estaba:
            self.favorite_user_ids.remove(user)
        return nuevo

    @classmethod
    def order_by_favorite(cls, queryset=None, user=None):
        """≙ ``_order_field_to_sql`` (``odoo19c: :239-247``) — D-3.

        La referencia emite ``id IN (SELECT picking_type_id FROM
        picking_type_favorite_user_rel WHERE user_id = %s)`` como expresión de
        orden. El equivalente exacto aquí es un ``Exists`` sobre la misma tabla
        de relación, y con él se completa ``is_favorite desc, sequence, id``.
        """
        queryset = cls.objects.all() if queryset is None else queryset
        if user is None:
            return queryset.order_by('sequence', 'id')
        rel = apps.get_model('stock', 'PickingTypeFavoriteUserRel')
        marcado = Exists(rel.objects.filter(
            picking_type_id=OuterRef('pk'), user_id=user.pk))
        return queryset.annotate(
            is_favorite=marcado).order_by('-is_favorite', 'sequence', 'id')

    # -- los conteos del tablero: sin columna, se calculan al leerse (D-2) --

    def get_picking_count(self):
        """≙ ``_compute_picking_count`` (``odoo19c: :254-270``).

        Devuelve el mismo diccionario de seis claves que la referencia asigna a
        seis campos calculados, con sus mismos dominios.
        """
        stock_picking = apps.get_model('stock', 'StockPicking')
        base = stock_picking.objects.filter(picking_type=self).exclude(
            state__in=('done', 'cancel'))
        hoy = datetime.date.today()
        abiertos = ('assigned', 'waiting', 'confirmed')
        return {
            'count_picking_draft': base.filter(state='draft').count(),
            'count_picking_waiting': base.filter(
                state__in=('confirmed', 'waiting')).count(),
            'count_picking_ready': base.filter(state='assigned').count(),
            'count_picking': base.filter(state__in=abiertos).count(),
            'count_picking_late': base.filter(state__in=abiertos).filter(
                Q(scheduled_date__lt=hoy) | Q(has_deadline_issue=True)).count(),
            'count_picking_backorders': base.filter(
                backorder__isnull=False,
                state__in=('confirmed', 'assigned', 'waiting')).count(),
        }

    @property
    def count_picking_draft(self):
        """≙ ``count_picking_draft`` (``odoo19c: :122``)."""
        return self.get_picking_count()['count_picking_draft']

    @property
    def count_picking_ready(self):
        """≙ ``count_picking_ready`` (``odoo19c: :123``)."""
        return self.get_picking_count()['count_picking_ready']

    @property
    def count_picking(self):
        """≙ ``count_picking`` (``odoo19c: :124``)."""
        return self.get_picking_count()['count_picking']

    @property
    def count_picking_waiting(self):
        """≙ ``count_picking_waiting`` (``odoo19c: :125``)."""
        return self.get_picking_count()['count_picking_waiting']

    @property
    def count_picking_late(self):
        """≙ ``count_picking_late`` (``odoo19c: :126``)."""
        return self.get_picking_count()['count_picking_late']

    @property
    def count_picking_backorders(self):
        """≙ ``count_picking_backorders`` (``odoo19c: :127``)."""
        return self.get_picking_count()['count_picking_backorders']

    @property
    def count_move_ready(self):
        """≙ ``count_move_ready`` / ``_compute_move_count`` (``:128``, ``:272-279``)."""
        stock_move = apps.get_model('stock', 'StockMove')
        return stock_move.objects.filter(
            picking_type=self, state='assigned').count()

    @property
    def hide_reservation_method(self):
        """≙ ``_compute_hide_reservation_method`` (``odoo19c: :249-252``)."""
        return self.code == CODE_INCOMING

    @property
    def show_picking_type(self):
        """≙ ``_compute_show_picking_type`` (``odoo19c: :365-368``)."""
        return self.code in (CODE_INCOMING, CODE_OUTGOING, CODE_INTERNAL)

    # -- los computes almacenados: se recalculan al guardar --

    def compute_use_create_lots(self):
        """≙ ``_compute_use_create_lots`` (``odoo19c: :290-294``)."""
        if self.code == CODE_INCOMING:
            self.use_create_lots = True
        return self.use_create_lots

    def compute_use_existing_lots(self):
        """≙ ``_compute_use_existing_lots`` (``odoo19c: :296-300``)."""
        if self.code == CODE_OUTGOING:
            self.use_existing_lots = True
        return self.use_existing_lots

    def compute_print_label(self):
        """≙ ``_compute_print_label`` (``odoo19c: :338-344``)."""
        if self.code in (CODE_INCOMING, CODE_INTERNAL):
            self.print_label = False
        elif self.code == CODE_OUTGOING:
            self.print_label = True
        return self.print_label

    def compute_warehouse(self):
        """≙ ``_compute_warehouse_id`` (``odoo19c: :355-363``).

        Con almacén ya puesto no se toca; si no, se toma el primero de la
        empresa.
        """
        if self.warehouse is not None or self.company is None:
            return self.warehouse
        stock_warehouse = apps.get_model('stock', 'StockWarehouse')
        self.warehouse = stock_warehouse.objects.filter(
            company=self.company).first()
        return self.warehouse

    def compute_default_location_src(self):
        """≙ ``_compute_default_location_src_id`` (``odoo19c: :316-325``).

        En una recepción el origen es la ubicación virtual de proveedores; en
        cualquier otro caso, el almacén de existencias.
        """
        if self.warehouse is None:
            self._warehouse_redirect_warning()
        if self.code == CODE_INCOMING:
            self.default_location_src = self._location_by_xmlid(
                XMLID_LOCATION_SUPPLIERS)
        else:
            self.default_location_src = (
                self.warehouse.lot_stock if self.warehouse is not None else None)
        return self.default_location_src

    def compute_default_location_dest(self):
        """≙ ``_compute_default_location_dest_id`` (``odoo19c: :327-336``).

        En una entrega el destino es la ubicación virtual de clientes; en
        cualquier otro caso, el almacén de existencias.
        """
        if self.warehouse is None:
            self._warehouse_redirect_warning()
        if self.code == CODE_OUTGOING:
            self.default_location_dest = self._location_by_xmlid(
                XMLID_LOCATION_CUSTOMERS)
        else:
            self.default_location_dest = (
                self.warehouse.lot_stock if self.warehouse is not None else None)
        return self.default_location_dest

    @staticmethod
    def _location_by_xmlid(xmlid):
        """Resuelve una ubicación por su identificador externo sembrado."""
        ir_model_data = apps.get_model('base', 'IrModelData')
        modulo, _sep, nombre = xmlid.partition('.')
        registro = ir_model_data.objects.filter(
            module=modulo, name=nombre).first()
        if registro is None:
            return None
        stock_location = apps.get_model('stock', 'StockLocation')
        return stock_location.objects.filter(pk=registro.res_id).first()

    @staticmethod
    def _warehouse_redirect_warning():
        """≙ ``stock.warehouse._warehouse_redirect_warning`` (``:318``, ``:329``).

        La referencia lanza el aviso que redirige a crear un almacén. Aquí se
        mantiene el punto de extensión con el mismo nombre; el redirect a la
        vista es cosa del cliente, que este stack no tiene.
        """
        return None

    def save(self, *args, **kwargs):
        """Dispara los computes almacenados, que allá corren por ``@api.depends``."""
        self.compute_use_create_lots()
        self.compute_use_existing_lots()
        self.compute_print_label()
        self.compute_warehouse()
        if self.default_location_src is None:
            self.compute_default_location_src()
        if self.default_location_dest is None:
            self.compute_default_location_dest()
        return super().save(*args, **kwargs)

    # -- los avisos que allá son @api.onchange (D-4) --

    def check_picking_code_warning(self, user):
        """≙ ``_onchange_picking_code`` (``odoo19c: :346-353``)."""
        if self.code == CODE_INTERNAL and not user.has_group(
                'stock.group_stock_multi_locations'):
            return {'warning': {'message': _(
                'Necesita activar las ubicaciones de almacenamiento para poder '
                'usar tipos de operación internos.')}}
        return None

    def check_sequence_code_warning(self):
        """≙ ``_onchange_sequence_code`` (``odoo19c: :394-406``).

        Avisa cuando otro tipo de operación ya usa ese prefijo con una
        secuencia distinta.
        """
        if not self.sequence_code:
            return None
        candidatos = type(self).objects.filter(
            Q(sequence_code=self.sequence_code),
            Q(company=self.company) | Q(company__isnull=True),
        )
        if self.pk is not None:
            candidatos = candidatos.exclude(pk=self.pk)
        otro = candidatos.first()
        if otro is not None and otro.sequence_id != self.sequence_id:
            return {'warning': {'message': _(
                'Otro tipo de operación ya usa este prefijo de secuencia. Se '
                'recomienda elegir un prefijo único para evitar referencias '
                'repetidas, o asignar a este tipo la secuencia existente.')}}
        return None

    # -- acciones de ventana (D-5) --

    @classmethod
    def action_redirect_to_barcode_installation(cls):
        """≙ ``action_redirect_to_barcode_installation`` (``odoo19c: :408-412``)."""
        accion = cls._action_by_xmlid('base.open_module_tree')
        if accion is not None:
            contexto = dict(accion.get('context') or {})
            contexto['search_default_name'] = 'Barcode'
            accion['context'] = contexto
        return accion

    @staticmethod
    def _action_by_xmlid(xmlid):
        """Lee el descriptor de una acción de ventana por identificador externo."""
        ir_model_data = apps.get_model('base', 'IrModelData')
        modulo, _sep, nombre = xmlid.partition('.')
        registro = ir_model_data.objects.filter(
            module=modulo, name=nombre).first()
        if registro is None:
            return None
        act_window = apps.get_model('base', 'IrActionsActWindow')
        accion = act_window.objects.filter(pk=registro.res_id).first()
        if accion is None:
            return None
        return {
            'type': 'ir.actions.act_window',
            'name': accion.name,
            'res_model': accion.res_model,
            'view_mode': accion.view_mode,
            'domain': accion.domain or [],
            'context': accion.get_context() if hasattr(
                accion, 'get_context') else {},
        }

    def get_action(self, action_xmlid):
        """≙ ``_get_action`` (``odoo19c: :414-441``).

        Fija el nombre visible, el contexto por defecto (tipo y empresa) y el
        dominio acotado al tipo. ``help`` se deja vacío hasta que exista el
        renderizador QWeb (tarea #273) — la clave se conserva para no cambiar
        la forma del descriptor.
        """
        accion = self._action_by_xmlid(action_xmlid)
        if accion is None:
            return None
        accion['display_name'] = str(self)
        contexto = dict(accion.get('context') or {})
        contexto.update({
            'default_picking_type_id': self.pk,
            'default_company_id': self.company_id,
        })
        accion['context'] = contexto
        accion['domain'] = [('picking_type_id', '=', self.pk)]
        accion['help'] = ''
        return accion

    def get_action_picking_tree_late(self):
        """≙ ``get_action_picking_tree_late`` (``odoo19c: :443-444``)."""
        return self.get_action('stock.action_picking_tree_late')

    def get_action_picking_tree_backorder(self):
        """≙ ``get_action_picking_tree_backorder`` (``odoo19c: :446-447``)."""
        return self.get_action('stock.action_picking_tree_backorder')

    def get_action_picking_tree_waiting(self):
        """≙ ``get_action_picking_tree_waiting`` (``odoo19c: :449-450``)."""
        return self.get_action('stock.action_picking_tree_waiting')

    def get_action_picking_tree_ready(self):
        """≙ ``get_action_picking_tree_ready`` (``odoo19c: :452-453``)."""
        return self.get_action('stock.action_picking_tree_ready')

    def get_action_picking_type_moves_analysis(self):
        """≙ ``get_action_picking_type_moves_analysis`` (``odoo19c: :455-460``)."""
        accion = self._action_by_xmlid('stock.stock_move_action')
        if accion is None:
            return None
        accion['domain'] = list(accion.get('domain') or []) + [
            ('picking_type_id', '=', self.pk)]
        return accion

    def get_stock_picking_action_picking_type(self):
        """≙ ``get_stock_picking_action_picking_type`` (``odoo19c: :462-470``)."""
        por_codigo = {
            CODE_INCOMING: 'stock.action_picking_tree_incoming',
            CODE_OUTGOING: 'stock.action_picking_tree_outgoing',
            CODE_INTERNAL: 'stock.action_picking_tree_internal',
        }
        return self.get_action(por_codigo.get(
            self.code, 'stock.stock_picking_action_picking_type'))

    def get_action_picking_type_ready_moves(self):
        """≙ ``get_action_picking_type_ready_moves`` (``odoo19c: :472-473``)."""
        return self.get_action('stock.action_get_picking_type_ready_moves')

    # -- el gráfico del tablero --

    @classmethod
    def get_aggregated_records_by_date(cls, picking_types):
        """≙ ``_get_aggregated_records_by_date`` (``odoo19c: :475-492``).

        Devuelve una terna por tipo: su id, las fechas previstas de sus
        transferencias abiertas, y el nombre de la serie de datos.
        """
        stock_picking = apps.get_model('stock', 'StockPicking')
        ids = [t.pk for t in picking_types]
        por_tipo = {i: [] for i in ids}
        abiertas = stock_picking.objects.filter(
            picking_type_id__in=ids,
            state__in=('assigned', 'waiting', 'confirmed'),
        ).values_list('picking_type_id', 'scheduled_date')
        for tipo_id, fecha in abiertas:
            por_tipo[tipo_id].append(fecha)
        return [(i, f, _('Transferencias')) for i, f in por_tipo.items()]

    @classmethod
    def prepare_graph_data(cls, summaries):
        """≙ ``_prepare_graph_data`` (``odoo19c: :494-525``).

        Convierte el resumen por categoría en la serie del gráfico. Si todos
        los valores son cero, la serie se marca como muestra.
        """
        categorias = {
            'total_before': {'label': _('Antes'), 'type': 'past'},
            'total_yesterday': {'label': _('Ayer'), 'type': 'past'},
            'total_today': {'label': _('Hoy'), 'type': 'present'},
            'total_day_1': {'label': _('Mañana'), 'type': 'future'},
            'total_day_2': {'label': _('Pasado mañana'), 'type': 'future'},
            'total_after': {'label': _('Después'), 'type': 'future'},
        }
        salida = {}
        for picking_type_id, resumen in summaries.items():
            vacio = all(resumen[k] == 0 for k in categorias)
            salida[picking_type_id] = [{
                'key': _('Datos de muestra') if vacio
                       else resumen['data_series_name'],
                'picking_type_id': None if vacio else picking_type_id,
                'values': [
                    dict(v, value=resumen[k],
                         type='sample' if vacio else v['type'])
                    for k, v in categorias.items()
                ],
            }]
        return salida

    @property
    def kanban_dashboard_graph(self):
        """≙ ``_compute_kanban_dashboard_graph`` (``odoo19c: :370-392``)."""
        stock_picking = apps.get_model('stock', 'StockPicking')
        agrupados = type(self).get_aggregated_records_by_date([self])
        resumenes = {}
        for picking_type_id, fechas, serie in agrupados:
            resumen = {
                'data_series_name': serie,
                'total_before': 0, 'total_yesterday': 0, 'total_today': 0,
                'total_day_1': 0, 'total_day_2': 0, 'total_after': 0,
            }
            for fecha in fechas:
                categoria = stock_picking.calculate_date_category(fecha)
                if categoria:
                    resumen['total_' + categoria] += 1
            resumenes[picking_type_id] = resumen
        return json.dumps(
            type(self).prepare_graph_data(resumenes).get(self.pk, []))

    def get_code_report_name(self):
        """≙ ``_get_code_report_name`` (``odoo19c: :527-535``)."""
        return {
            CODE_OUTGOING: _('Nota de entrega'),
            CODE_INCOMING: _('Nota de recepción'),
            CODE_INTERNAL: _('Movimiento interno'),
        }.get(self.code)


class PickingTypeFavoriteUserRel(models.Model):
    """Tabla de relación ``picking_type_favorite_user_rel`` — tipo ↔ usuario.

    La referencia la declara con sus nombres de columna explícitos
    (``odoo19c: addons/stock/models/stock_picking.py:144-146`` —
    ``favorite_user_ids = fields.Many2many('res.users',
    'picking_type_favorite_user_rel', 'picking_type_id', 'user_id')``), y su
    ``_order_field_to_sql`` (``:239-247``) consulta esa tabla por su nombre. El
    ``through`` explícito existe para fijar los tres nombres.
    """

    picking_type = fields.Many2one(
        StockPickingType, on_delete=models.CASCADE,
        db_column='picking_type_id', related_name='+',
        verbose_name='Tipo de operación',
    )
    user = fields.Many2one(
        ResUsers, on_delete=models.CASCADE, db_column='user_id',
        related_name='+', verbose_name='Usuario',
    )

    class Meta:
        db_table = 'picking_type_favorite_user_rel'
        constraints = [
            models.UniqueConstraint(
                fields=['picking_type', 'user'],
                name='picking_type_favorite_user_rel_uniq'),
        ]
        verbose_name = 'Tipo de operación favorito'
        verbose_name_plural = 'Tipos de operación favoritos'

    def __str__(self) -> str:
        return f'{self.picking_type_id}:{self.user_id}'


class StockPicking(TimeStampedModel):
    """``stock.picking`` — una transferencia (albarán).

    .. warning:: Porte parcial declarado — 5 de 57 campos, 4 de 97 métodos.

       La referencia declara ``StockPicking`` en
       ``odoo19c: addons/stock/models/stock_picking.py:538-2149``: **154
       símbolos**. Este esbozo trae el núcleo que el resto del árbol ya usa
       (``name``/``state``/las dos ubicaciones/la orden de venta y la máquina de
       transiciones). El porte completo es el paso siguiente de la tarea
       **#330**; hasta entonces la cobertura queda declarada aquí y no se
       presenta como terminada (``porte-completo-no-parcial.md``).
    """

    _name = 'stock.picking'
    _description = "Transfer"

    STATE_DRAFT     = 'draft'
    STATE_WAITING   = 'waiting'
    STATE_CONFIRMED = 'confirmed'
    STATE_ASSIGNED  = 'assigned'
    STATE_DONE      = 'done'
    STATE_CANCEL    = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Borrador'),
        (STATE_WAITING, 'Esperando otro movimiento'),
        (STATE_CONFIRMED, 'Esperando'),
        (STATE_ASSIGNED, 'Disponible'),
        (STATE_DONE, 'Hecho'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    name             = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Referencia (Odoo stock.picking.name).',
    )
    state            = fields.Selection(
        max_length=16, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado (Odoo stock.picking.state).',
    )
    location         = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pickings_out', help_text='Origen (Odoo location_id).',
    )
    location_dest    = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pickings_in', help_text='Destino (Odoo location_dest_id).',
    )
    # Odoo stock.picking.sale_id — el enlace lo añade el módulo sale_stock
    # (stock_picking se inherita en sale_stock/models/stock_picking.py). Aquí el
    # albarán conoce su orden de venta canónica; el sub-estado de preparación
    # (state confirmed/assigned) se proyecta a IN_PREPARATION cuando aún no hay
    # guía de transportista (V5a de analisis-unificar-orders-sale, H-SALE-09).
    sale_order       = fields.Many2one(
        'sale.SaleOrder', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pickings', help_text='Orden de venta (Odoo stock.picking.sale_id).',
    )

    class Meta:
        db_table = 'stock_picking'
        ordering = ['-created_at', '-id']
        verbose_name = 'Transferencia de inventario'
        verbose_name_plural = 'Transferencias de inventario'

    def __str__(self) -> str:
        return self.name or f'{self.state}:{self.pk}'

    def action_confirm(self):
        """Confirma la transferencia y sus movimientos (Odoo action_confirm)."""
        if not self.name:
            self.name = f'WH/{uuid.uuid4().hex[:8].upper()}'
        self.state = self.STATE_CONFIRMED
        self.save(update_fields=['name', 'state', 'updated_at'])
        for move in self.move_ids.all():
            move._action_confirm()
        return self

    def action_assign(self):
        """Reserva/asigna la disponibilidad (Odoo action_assign)."""
        self.state = self.STATE_ASSIGNED
        self.save(update_fields=['state', 'updated_at'])
        for move in self.move_ids.all():
            move._action_assign()
        return self

    def button_validate(self):
        """Valida la transferencia → hecho (Odoo button_validate)."""
        for move in self.move_ids.all():
            move._action_done()
        self.state = self.STATE_DONE
        self.save(update_fields=['state', 'updated_at'])
        return self

    def action_cancel(self):
        """Cancela la transferencia (Odoo action_cancel)."""
        self.state = self.STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])
        for move in self.move_ids.all():
            move._action_cancel()
        return self
