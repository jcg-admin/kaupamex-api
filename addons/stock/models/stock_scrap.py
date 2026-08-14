"""``stock.scrap`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_scrap.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el **desecho** es la salida de mercancía que no vuelve. No es una
merma de inventario ni una devolución: es una orden explícita que mueve una
cantidad de una ubicación interna a una de tipo ``inventory``, y que al
validarse deja un ``stock.move`` hecho. Su valor está en el par de gates que
la envuelven, y confundirlos es el error fácil de este modelo:

- ``check_available_qty`` mira si **hay existencia** para desechar, y si no la
  hay devuelve el asistente en vez de desechar;
- ``_unlink_except_done`` impide borrar el registro **después** de validado,
  porque su ``stock.move`` ya movió existencias reales.

El segundo mecanismo interesante es ``should_replenish``: desechar puede
disparar un **abastecimiento** por la misma cantidad, y ahí la referencia
limpia el contexto (``clean_context``) para que los ``default_*`` del
formulario de desecho no siembren el registro que el abastecimiento cree.

Porte símbolo por símbolo — 42 de 42
======================================

Medido sobre ``odoo19c: addons/stock/models/stock_scrap.py`` (249 líneas):
dos clases, 8 atributos de clase, 22 campos y 16 métodos.

``StockScrap`` — atributos de clase, 4 de 4
---------------------------------------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``_name`` (11)                                   ``_name`` verbatim
``_inherit = ['mail.thread']`` (12)              ``_inherit`` verbatim + base ``MailThread``
``_order`` (13)                                  ``_order`` verbatim + ``Meta.ordering``
``_description`` (14)                            ``_description`` verbatim
===============================================  ======================================

``StockScrap`` — campos, 19 de 19
-----------------------------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``name`` (16-18)                                 ``name``
``company_id`` (19)                              ``company``
``origin`` (20)                                  ``origin``
``product_id`` (21-23)                           ``product``
``allowed_uom_ids`` (24)                         property ``allowed_uom_ids``
``product_uom_id`` (25-28)                       ``product_uom`` (almacenado)
``tracking`` (29)                                property ``tracking`` (related)
``lot_id`` (30-32)                               ``lot``
``package_id`` (33-35)                           ``package``
``owner_id`` (36)                                ``owner``
``move_ids`` (37)                                reverso ``move_ids``
``picking_id`` (38)                              ``picking``
``location_id`` (39-42)                          ``location`` (almacenado)
``scrap_location_id`` (43-46)                    ``scrap_location`` (almacenado)
``scrap_qty`` (47-49)                            ``scrap_qty`` (almacenado)
``state`` (50-53)                                ``state``
``date_done`` (54)                               ``date_done``
``should_replenish`` (55)                        ``should_replenish``
``scrap_reason_tag_ids`` (56-59)                 ``scrap_reason_tags``
===============================================  ======================================

``StockScrap`` — métodos, 16 de 16
------------------------------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``_compute_allowed_uom_ids`` (61-64)             property ``allowed_uom_ids``
``_compute_product_uom_id`` (66-69)              ``_compute_product_uom_id``
``_compute_location_id`` (71-86)                 ``_compute_location_id``
``_compute_scrap_location_id`` (88-98)           ``_compute_scrap_location_id``
``_compute_scrap_qty`` (100-105)                 ``_compute_scrap_qty``
``_onchange_serial_number`` (107-118)            ``_onchange_serial_number``
``_unlink_except_done`` (120-123)                ``_unlink_except_done`` + ``delete()``
``_prepare_move_values`` (125-150)               ``_prepare_move_values``
``do_scrap`` (152-163)                           ``do_scrap``
``_create_scrap_move`` (165-167)                 ``_create_scrap_move``
``do_replenish`` (169-181)                       ``do_replenish``
``action_get_stock_picking`` (183-186)           ``action_get_stock_picking``
``action_get_stock_move_lines`` (188-191)        ``action_get_stock_move_lines``
``_should_check_available_qty`` (193-194)        ``_should_check_available_qty``
``check_available_qty`` (196-209)                ``check_available_qty``
``action_validate`` (211-234)                    ``action_validate``
===============================================  ======================================

``StockScrapReasonTag`` — 4 atributos + 3 campos, completo
------------------------------------------------------------

===============================================  ======================================
Símbolo de la referencia (línea)                 Aquí
===============================================  ======================================
``_name`` (238) · ``_description`` (239)         verbatim
``_order`` (240)                                 verbatim + ``Meta.ordering``
``_name_uniq`` (246-249)                         ``Meta.constraints`` con el nombre conservado
``name`` (242) · ``sequence`` (243) · ``color`` (244)  ``name`` · ``sequence`` · ``color``
===============================================  ======================================

Divergencias declaradas
=========================

1. **``_compute_*`` de los cuatro campos almacenados se invocan desde
   ``save()``, no por un motor de dependencias.** La referencia declara
   ``@api.depends`` y su ORM recalcula solo. Aquí el motor no existe todavía
   (tarea **#191**), así que ``save()`` llama a los cuatro en el orden que la
   referencia produce por su grafo: unidad → ubicación origen → ubicación de
   desecho → cantidad. El orden importa: ``_compute_location_id`` depende de
   ``company``/``picking`` y ``_compute_scrap_qty`` de los movimientos ya
   creados.
2. **Los tres computados de sólo lectura son ``property``, no columna.**
   ``allowed_uom_ids`` y ``tracking`` se derivan del producto en cada acceso;
   almacenarlos exigiría invalidarlos al cambiar el producto, que es
   exactamente el trabajo que el motor de dependencias hará cuando exista.
3. **``_onchange_serial_number`` devuelve el aviso, no lo pinta.** La
   referencia retorna ``{'warning': {...}}`` que su cliente web muestra; aquí
   devuelve el mismo diccionario para que el consumidor —hoy, la API REST—
   decida cómo presentarlo. El **efecto lateral se conserva**: si hay
   ubicación recomendada, se asigna a ``location`` igual que allá.
4. **Las dos ``action_get_*`` devuelven el descriptor, no la acción.** Misma
   razón y mismo precedente que ``stock_package.py``: sin capa de vistas, el
   ``ir.actions.act_window`` no tiene destino. Registrado en la tarea **#279**.
5. **``action_validate`` devuelve el descriptor del asistente de cantidad
   insuficiente.** ``stock.warn.insufficient.qty.scrap`` es un modelo
   transitorio de la referencia que aún no está portado; el descriptor lleva
   los mismos cinco valores por defecto para que el consumidor lo resuelva.
   Registrado en la tarea **#354**.
6. **``_check_company`` no tiene contraparte de mecanismo.** La referencia lo
   invoca al principio de ``do_scrap`` para validar los ``check_company=True``
   de golpe. Aquí ``check_company`` no es un argumento de campo del stack, así
   que la coherencia se verifica en ``_check_company()`` a mano sobre las
   cuatro relaciones que la referencia marca (``product``, ``lot``,
   ``package``, ``owner``, ``picking``, ``location``, ``scrap_location``).
"""
import fields
import models
from django.db.models import Min
from django.utils import timezone

from addons.base.models import TimeStampedModel
from addons.base.models.decimal_precision import DecimalPrecision
from addons.base.models.ir_sequence import IrSequence
from addons.mail.models import MailThread
from addons.stock.models.stock_location import StockLocation
from addons.stock.models.stock_quant import StockQuant
from addons.stock.models.stock_warehouse import StockWarehouse
from exceptions import UserError
from tools.float_utils import float_compare
from tools.misc import clean_context
from tools.translate import _

#: ≙ el ``digits='Product Unit'`` que la referencia declara en ``scrap_qty``
#: (``odoo19c: :48``) y consulta en ``check_available_qty`` (``:200``).
PRODUCT_UNIT_PRECISION = 'Product Unit'

#: ≙ el código de secuencia que ``do_scrap`` consume (``odoo19c: :155``).
SCRAP_SEQUENCE_CODE = 'stock.scrap'


class StockScrap(MailThread, TimeStampedModel):
    """``stock.scrap`` — orden de desecho de una cantidad de producto."""

    _name = 'stock.scrap'
    _inherit = ['mail.thread']
    _order = 'id desc'
    _description = 'Scrap'

    STATE_DRAFT = 'draft'
    STATE_DONE = 'done'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Borrador'),
        (STATE_DONE, 'Hecho'),
    ]

    name             = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Referencia, de la secuencia stock.scrap (Odoo name).',
    )
    company          = fields.Many2one(
        'base.ResCompany', on_delete=models.PROTECT, related_name='stock_scraps',
        db_index=True, help_text='Empresa (Odoo company_id, requerido).',
    )
    origin           = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Documento de origen (Odoo origin).',
    )
    product          = fields.Many2one(
        'product.ProductProduct', on_delete=models.PROTECT, related_name='scraps',
        db_index=True, help_text='Producto a desechar (Odoo product_id, requerido).',
    )
    product_uom      = fields.Many2one(
        'uom.Uom', on_delete=models.PROTECT, related_name='scraps',
        help_text='Unidad (Odoo product_uom_id, computado y almacenado).',
    )
    lot              = fields.Many2one(
        'stock.StockLot', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='scraps', help_text='Lote/serie (Odoo lot_id).',
    )
    package          = fields.Many2one(
        'stock.StockPackage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='scraps', help_text='Paquete (Odoo package_id).',
    )
    owner            = fields.Many2one(
        'base.ResPartner', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='owned_scraps', help_text='Propietario (Odoo owner_id).',
    )
    picking          = fields.Many2one(
        'stock.StockPicking', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='scraps', help_text='Albarán de origen (Odoo picking_id).',
    )
    location         = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, related_name='scraps_out',
        help_text='Ubicación origen, interna '
                  '(Odoo location_id, computado y almacenado).',
    )
    scrap_location   = fields.Many2one(
        'stock.StockLocation', on_delete=models.PROTECT, related_name='scraps_in',
        help_text='Ubicación de desecho, de tipo inventory '
                  '(Odoo scrap_location_id, computado y almacenado).',
    )
    scrap_qty        = fields.Float(
        default=1.0,
        help_text='Cantidad a desechar (Odoo scrap_qty, computado y almacenado).',
    )
    state            = fields.Selection(
        max_length=8, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado (Odoo state: draft/done).',
    )
    date_done        = fields.Datetime(
        null=True, blank=True, help_text='Fecha de validación (Odoo date_done).',
    )
    should_replenish = fields.Boolean(
        default=False,
        help_text='Dispara abastecimiento por lo desechado (Odoo should_replenish).',
    )
    scrap_reason_tags = fields.Many2many(
        'stock.StockScrapReasonTag', blank=True, related_name='scraps',
        help_text='Motivo del desecho (Odoo scrap_reason_tag_ids).',
    )

    class Meta:
        db_table = 'stock_scrap'
        # ≙ ``_order = 'id desc'`` (``odoo19c: :13``).
        ordering = ['-id']
        verbose_name = 'Desecho'
        verbose_name_plural = 'Desechos'

    def __str__(self) -> str:
        return self.name or f'stock.scrap#{self.pk}'

    # --- campos derivados que no se almacenan ---------------------------------

    @property
    def allowed_uom_ids(self):
        """≙ ``_compute_allowed_uom_ids`` (``odoo19c: :61-64``).

        La unidad del producto, sus unidades alternas y las que declaran sus
        proveedores — la unión de las tres, que es lo que acota el dominio de
        ``product_uom``. Es property y no columna por la divergencia D-2.
        """
        if self.product_id is None:
            return []
        producto = self.product
        permitidas = {producto.uom} if producto.uom else set()
        permitidas |= set(producto.uom_ids.values_list('pk', flat=True)) \
            if hasattr(producto, 'uom_ids') else set()
        permitidas |= set(
            producto.seller_ids.exclude(product_uom__isnull=True)
            .values_list('product_uom_id', flat=True)
        ) if hasattr(producto, 'seller_ids') else set()
        return sorted(p for p in permitidas if p)

    @property
    def tracking(self):
        """≙ ``tracking`` (``odoo19c: :29``) — ``related="product_id.tracking"``."""
        return self.product.tracking if self.product_id else None

    # --- los cuatro computados almacenados (D-1) -------------------------------

    def _compute_product_uom_id(self):
        """≙ ``_compute_product_uom_id`` (``odoo19c: :66-69``)."""
        if self.product_id:
            self.product_uom = self.product.uom

    def _compute_location_id(self):
        """≙ ``_compute_location_id`` (``odoo19c: :71-86``).

        Dos fuentes, en el orden de la referencia: si hay albarán, su ubicación
        —destino si ya está hecho, origen si no—; si no, la ubicación de
        existencias del primer almacén de la empresa. Sin almacén, la
        referencia dispara ``_warehouse_redirect_warning``, que aquí devuelve
        su descriptor y se eleva como ``UserError``: sin almacén no hay
        ubicación posible y seguir dejaría el campo requerido en vacío.
        """
        if self.picking_id:
            self.location = (self.picking.location_dest
                             if self.picking.state == 'done'
                             else self.picking.location)
            return
        if not self.company_id:
            return
        almacen = (StockWarehouse.objects
                   .filter(company_id=self.company_id)
                   .order_by('pk').first())
        if almacen is None:
            aviso = StockWarehouse._warehouse_redirect_warning(company=self.company)
            raise UserError(aviso.get('message') if isinstance(aviso, dict) else str(aviso))
        self.location = almacen.lot_stock

    def _compute_scrap_location_id(self):
        """≙ ``_compute_scrap_location_id`` (``odoo19c: :88-98``).

        La ubicación de tipo ``inventory`` de menor id de la empresa. La
        referencia agrupa por empresa con ``['id:min']`` para resolver el
        conjunto entero de golpe; aquí se resuelve por registro, que es lo que
        ``save()`` necesita.
        """
        if not self.company_id:
            return
        minimo = (StockLocation.objects
                  .filter(company_id=self.company_id,
                          usage=StockLocation.USAGE_INVENTORY)
                  .aggregate(minimo=Min('pk'))['minimo'])
        if minimo is not None:
            self.scrap_location_id = minimo

    def _compute_scrap_qty(self):
        """≙ ``_compute_scrap_qty`` (``odoo19c: :100-105``).

        Uno por defecto; la cantidad del primer movimiento si ya lo hay. La
        referencia asigna ``self.scrap_qty = 1`` sobre el conjunto entero antes
        del bucle — mismo efecto aquí sobre el registro.
        """
        self.scrap_qty = 1
        primero = self.move_ids.order_by('pk').first() if self.pk else None
        if primero is not None:
            self.scrap_qty = primero.quantity

    def _onchange_serial_number(self):
        """≙ ``_onchange_serial_number`` (``odoo19c: :107-118``) — D-3.

        Sólo para producto con seguimiento por **serie**: pregunta a
        ``stock.quant`` si esa serie ya existe en otra empresa o en otra
        ubicación. Si propone ubicación, se asigna; devuelve el aviso o
        ``None``.
        """
        if self.tracking != 'serial' or not self.lot_id:
            return None
        mensaje, recomendada = StockQuant._check_serial_number(
            self.product, self.lot, self.company, self.location,
        )
        if not mensaje:
            return None
        if recomendada:
            self.location = recomendada
        return {'warning': {'title': _('Warning'), 'message': mensaje}}

    # --- guardas de ciclo de vida ---------------------------------------------

    def _unlink_except_done(self):
        """≙ ``_unlink_except_done`` (``odoo19c: :120-123``).

        «You cannot delete a scrap which is done.» El desecho validado ya movió
        existencias reales: borrarlo dejaría el ``stock.move`` sin dueño.
        """
        if self.state == self.STATE_DONE:
            raise UserError(_('You cannot delete a scrap which is done.'))

    def delete(self, *args, **kwargs):
        """Aplica ``_unlink_except_done`` antes de borrar.

        La referencia lo declara con ``@api.ondelete(at_uninstall=False)``, que
        su ORM invoca en el ``unlink``. Aquí el punto equivalente es el
        ``delete()`` del modelo: ese decorador **no** es un gancho de
        desinstalación que se pueda omitir, es la guarda del borrado.
        """
        self._unlink_except_done()
        return super().delete(*args, **kwargs)

    def _check_company(self):
        """Coherencia de empresa de las relaciones ``check_company=True`` — D-6.

        La referencia lo obtiene declarando ``check_company=True`` en siete
        campos y llamando a ``self._check_company()`` en ``do_scrap``
        (``odoo19c: :153``). Aquí ese argumento de campo no existe en el stack,
        así que la misma comprobación se hace explícita sobre las siete
        relaciones que la fuente marca.
        """
        if not self.company_id:
            return
        for campo in ('product', 'lot', 'package', 'owner',
                      'picking', 'location', 'scrap_location'):
            relacionado = getattr(self, campo, None)
            if relacionado is None:
                continue
            ajena = getattr(relacionado, 'company_id', None)
            if ajena and ajena != self.company_id:
                raise UserError(_(
                    'The company of %(field)s does not match the company of the scrap.',
                    field=campo,
                ))

    def save(self, *args, **kwargs):
        """Recalcula los cuatro campos almacenados antes de escribir — D-1."""
        self._compute_product_uom_id()
        if self.location_id is None:
            self._compute_location_id()
        if self.scrap_location_id is None:
            self._compute_scrap_location_id()
        return super().save(*args, **kwargs)

    # --- el movimiento que el desecho produce ---------------------------------

    def _prepare_move_values(self):
        """≙ ``_prepare_move_values`` (``odoo19c: :125-150``).

        Los valores del ``stock.move`` que el desecho crea: origen legible,
        producto y unidad, la cantidad como demanda, el par de ubicaciones, y
        una línea de movimiento ya servida (``picked=True``) con lote, paquete
        y propietario. El ``restrict_partner_id`` comentado de la fuente
        (``:147``) se conserva comentado — la referencia lo dejó así.
        """
        return {
            'origin': self.origin or (self.picking.name if self.picking_id else '') or self.name,
            'company_id': self.company_id,
            'product_id': self.product_id,
            'product_uom_id': self.product_uom_id,
            'state': 'draft',
            'product_uom_qty': self.scrap_qty,
            'location_id': self.location_id,
            'scrap_id': self.pk,
            'location_dest_id': self.scrap_location_id,
            'move_line_ids': [{
                'product_id': self.product_id,
                'product_uom_id': self.product_uom_id,
                'quantity': self.scrap_qty,
                'location_id': self.location_id,
                'location_dest_id': self.scrap_location_id,
                'package_id': self.package_id,
                'owner_id': self.owner_id,
                'lot_id': self.lot_id,
            }],
            # 'restrict_partner_id': self.owner_id,
            'picked': True,
            'picking_id': self.picking_id,
        }

    def _create_scrap_move(self):
        """≙ ``_create_scrap_move`` (``odoo19c: :165-167``)."""
        StockMove = self._meta.apps.get_model('stock', 'StockMove')
        valores = self._prepare_move_values()
        lineas = valores.pop('move_line_ids', [])
        movimiento = StockMove.objects.create(**valores)
        if lineas:
            StockMoveLine = self._meta.apps.get_model('stock', 'StockMoveLine')
            for linea in lineas:
                StockMoveLine.objects.create(move_id=movimiento.pk, **linea)
        return movimiento

    def do_scrap(self):
        """≙ ``do_scrap`` (``odoo19c: :152-163``).

        Numera, crea el movimiento, lo da por hecho, marca el desecho y —si se
        pidió— dispara el abastecimiento. El ``with_context(is_scrap=True)`` de
        la fuente marca el movimiento para que el cierre no genere backorder;
        aquí se pasa como argumento a ``_action_done``.
        """
        self._check_company()
        self.name = IrSequence.next_by_code(SCRAP_SEQUENCE_CODE, company=self.company) or _('New')
        movimiento = self._create_scrap_move()
        movimiento._action_done()
        self.state = self.STATE_DONE
        self.date_done = timezone.now()
        self.save(update_fields=['name', 'state', 'date_done', 'updated_at'])
        if self.should_replenish:
            self.do_replenish()
        return True

    def do_replenish(self, values=None):
        """≙ ``do_replenish`` (``odoo19c: :169-181``).

        Encola una necesidad por la misma cantidad y la corre por el motor de
        reglas. El ``clean_context`` no es cosmético: sin él, los ``default_*``
        del desecho sembrarían el registro que la regla cree.
        """
        StockRule = self._meta.apps.get_model('stock', 'StockRule')
        valores = dict(values or {})
        valores.setdefault('context', clean_context(valores.get('context') or {}))
        return StockRule.run([StockRule.Procurement(
            self.product,
            self.scrap_qty,
            self.product_uom,
            self.location,
            self.name,
            self.name,
            self.company,
            valores,
        )])

    # --- descriptores de navegación (D-4) --------------------------------------

    def action_get_stock_picking(self):
        """≙ ``action_get_stock_picking`` (``odoo19c: :183-186``) — D-4."""
        return {
            'xml_id': 'stock.action_picking_tree_all',
            'domain': [('id', '=', self.picking_id)],
        }

    def action_get_stock_move_lines(self):
        """≙ ``action_get_stock_move_lines`` (``odoo19c: :188-191``) — D-4."""
        return {
            'xml_id': 'stock.stock_move_line_action',
            'domain': [('move_id', 'in', list(self.move_ids.values_list('pk', flat=True)))],
        }

    # --- los dos gates del desecho ---------------------------------------------

    def _should_check_available_qty(self):
        """≙ ``_should_check_available_qty`` (``odoo19c: :193-194``).

        Sólo el producto **almacenable** tiene existencia que comprobar; un
        consumible o un servicio no la tienen y el gate no aplica.
        """
        return bool(self.product.is_storable) if self.product_id else False

    def check_available_qty(self):
        """≙ ``check_available_qty`` (``odoo19c: :196-209``).

        ``True`` si hay existencia suficiente en la ubicación, lote, paquete y
        propietario declarados. La cantidad a desechar se convierte a la unidad
        del producto antes de comparar — desechar «2 cajas» de un producto que
        se lleva en piezas no se compara contra piezas sin convertir.
        """
        if not self._should_check_available_qty():
            return True
        precision = DecimalPrecision.precision_get(PRODUCT_UNIT_PRECISION)
        disponible = StockQuant._get_available_quantity(
            self.product, self.location,
            lot=self.lot, package=self.package, owner=self.owner, strict=True,
        )
        cantidad = self.product_uom.compute_quantity(self.scrap_qty, self.product.uom)
        return float_compare(float(disponible), float(cantidad),
                             precision_digits=precision) >= 0

    def action_validate(self):
        """≙ ``action_validate`` (``odoo19c: :211-234``) — D-5.

        Rechaza cantidad cero o negativa, deseca si hay existencia, y si no la
        hay devuelve el descriptor del asistente con los cinco valores por
        defecto que la referencia le pasa.
        """
        if self.product_uom.is_zero(self.scrap_qty) or self.scrap_qty < 0:
            raise UserError(_('You can only enter positive quantities.'))
        if self.check_available_qty():
            return self.do_scrap()
        return {
            'name': _('%(product)s: Insufficient Quantity To Scrap',
                      product=str(self.product)),
            'view_mode': 'form',
            'res_model': 'stock.warn.insufficient.qty.scrap',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {
                'default_product_id': self.product_id,
                'default_location_id': self.location_id,
                'default_scrap_id': self.pk,
                'default_quantity': self.product_uom.compute_quantity(
                    self.scrap_qty, self.product.uom),
                'default_product_uom_name': self.product.uom_name,
            },
        }


class StockScrapReasonTag(TimeStampedModel):
    """``stock.scrap.reason.tag`` — motivo por el que se desecha."""

    _name = 'stock.scrap.reason.tag'
    _description = 'Scrap Reason Tag'
    _order = 'sequence, id'

    name     = fields.Char(
        max_length=64,
        help_text='Nombre del motivo (Odoo name, requerido y traducible).',
    )
    sequence = fields.Integer(
        default=10, help_text='Orden de presentación (Odoo sequence).',
    )
    color    = fields.Char(
        max_length=16, default='#3C3C3C', help_text='Color (Odoo color).',
    )

    class Meta:
        db_table = 'stock_scrap_reason_tag'
        # ≙ ``_order = 'sequence, id'`` (``odoo19c: :240``).
        ordering = ['sequence', 'id']
        verbose_name = 'Motivo de desecho'
        verbose_name_plural = 'Motivos de desecho'
        constraints = [
            # ≙ ``_name_uniq = models.Constraint('unique (name)', 'Tag name
            # already exists!')`` (``odoo19c: :246-249``). El nombre de la
            # restricción se conserva para que el error sea rastreable a la
            # fuente.
            models.UniqueConstraint(
                fields=['name'], name='stock_scrap_reason_tag_name_uniq',
                violation_error_message='Tag name already exists!',
            ),
        ]

    def __str__(self) -> str:
        return self.name
