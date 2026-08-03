"""Modelo ``SaleOrder`` — addon ``sale``.

Adaptación fiel del módulo Odoo ``sale`` (``sale/models/sale_order.py``). En
Odoo **no existe un modelo "cart"**: el carrito es un ``sale.order`` con
``state='draft'`` (``website_sale``) y la orden confirmada es ``state='sale'``.
Este addon es el modelo canónico que **absorbe** la divergencia ``cart`` +
``orders`` (ver ``analisis-unificar-cart-order-sale``).

Fidelidad de scope: se portan los campos comerciales core de ``sale.order``
(``name``/``partner_id``/``state``/``date_order``/``order_line`` + amounts). Los
estados de *fulfillment* (enviado/entregado) y *pago* (pagado) NO viven aquí — en
Odoo están en ``stock.picking`` y ``payment.transaction``/``account.move``; se
integran en sus addons (``inventory``/``logistics``/``payments``).
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
import api
import fields
import models
from django.db import transaction
from django.utils import timezone

from exceptions import UserError
from tools.translate import _

from addons.account.services import create_invoice_from_sale_order
from addons.base.models import IrSequence, TimeStampedModel
from addons.platform.models import CompanyScopedManager
from addons.mail.models import MailThread


def _next_sale_name() -> str:
    """Referencia SO vía ``ir.sequence`` ``code='sale.order'`` (Odoo
    ``sale/models/sale_order.py:1010`` — ``next_by_code('sale.order')``;
    secuencia ``seq_sale_order``: prefix ``S``, padding 5 → ``S00001``,
    ``sale/data/ir_sequence_data.xml``). El seed es idempotente en el punto
    de uso — análogo del data record ``noupdate`` — para no depender del
    mecanismo de seeds del proyecto (H-API-22). ``select_for_update``
    serializa la lectura-incremento; el atomic anidado lo hace válido
    aunque el llamador no tenga transacción abierta.
    """
    with transaction.atomic():
        seq = IrSequence.objects.select_for_update().filter(
            code='sale.order').first()
        if seq is None:
            seq = IrSequence.objects.create(
                name='Sales Order', code='sale.order', prefix='S', padding=5)
        return seq.get_next()


class SaleOrder(MailThread, TimeStampedModel):
    """``sale.order`` — cotización/carrito (draft) → orden de venta (sale).

    Hereda ``MailThread`` igual que ``sale.order`` hereda ``mail.thread`` en la
    referencia (``odoo19x sale/models/sale_order.py:23``). El mixin es abstracto
    y **no agrega columnas** —el hilo se materializa en ``mail_message`` /
    ``mail_followers`` por el par polimórfico—, así que la herencia no genera
    migración.

    Por qué importa para el cut-over: en la referencia la bitácora de la venta
    es ``tracking=True`` sobre ``state`` (``:81``), no una tabla lateral. El
    espejo ``orders.Order`` sí era un hilo; la canónica no lo era, de modo que
    retirar ``orders`` habría perdido la capacidad.
    """

    # Odoo SALE_ORDER_STATE (sale/models/sale_order.py:70, default 'draft').
    STATE_DRAFT  = 'draft'    # cotización / carrito (website_sale)
    STATE_SENT   = 'sent'     # cotización enviada
    STATE_SALE   = 'sale'     # orden de venta confirmada
    STATE_CANCEL = 'cancel'
    STATES = [
        (STATE_DRAFT,  'Cotización'),
        (STATE_SENT,   'Cotización enviada'),
        (STATE_SALE,   'Orden de venta'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    # DEC-003: ``TimeStampedModel`` deja ``created_at`` sin índice y encarga a
    # cada modelo declararlo "por volumen (inventario, órdenes)". El espejo lo
    # declaraba y la canónica no lo heredó al retirarlo, aunque es ella la que
    # se ordena por fecha en el panel del comprador y en el admin.
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # ``name`` NULL mientras es borrador (Odoo lo asigna al crear vía secuencia;
    # aquí se asigna al confirmar). UNIQUE admite múltiples NULL en SQL.
    name       = fields.Char(
        max_length=20, unique=True, null=True, blank=True, db_index=True,
        help_text='Referencia SO (Odoo sale.order.name). NULL en borrador.',
    )
    partner    = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_orders',
        help_text='Cliente (Odoo partner_id). NULL en carrito anónimo.',
    )
    cart_token = models.UUIDField(
        unique=True, null=True, blank=True, db_index=True,
        help_text='Carrito anónimo — draft sin partner (paridad cart.cart_token).',
    )
    state      = fields.Selection(
        max_length=10, choices=STATES, default=STATE_DRAFT, db_index=True,
    )
    date_order = fields.Datetime(
        null=True, blank=True,
        help_text='Fecha de la orden (Odoo date_order); se fija al confirmar.',
    )
    locked     = fields.Boolean(
        default=False, help_text='Orden bloqueada, no modificable (Odoo locked).',
    )
    # Odoo sale.order.team_id (Many2one crm.team) — atribución de la orden a un
    # equipo de venta. El addon ``sale`` declara ``sales_team`` como dependencia
    # justamente para añadir este campo.
    team       = fields.Many2one(
        'sales_team.CrmTeam', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_orders',
        help_text='Equipo de venta atribuido (Odoo sale.order.team_id).',
    )
    # V1 unificación orders→sale (DEC-FW-02): lo que el flujo vivo del
    # strangler ``orders.Order`` necesita y el canónico aún no tenía.
    # guest_email = checkout anónimo (BR-011); en Odoo el guest es un
    # partner efímero de website_sale — aquí se conserva el email snapshot.
    guest_email = fields.Char(
        max_length=254, blank=True, default='',
        help_text='Email del comprador anónimo (BR-011). Vacío si hay partner.',
    )
    notes       = fields.Text(
        blank=True, default='',
        help_text='Notas del comprador al confirmar (paridad orders.Order.notes).',
    )
    # Empresa dueña de la orden (Odoo sale.order.company_id). L3 rollout
    # SOL-085 S3: nullable durante el backfill (la migración asigna las filas
    # heredadas a la founder company). Espeja el patrón de company.CompanySetting.
    company     = fields.Many2one(
        'platform.Company', null=True, blank=True,
        on_delete=models.CASCADE, related_name='sale_orders',
        help_text='Empresa dueña de la orden (Odoo company_id). NULL pre-backfill.',
    )

    # Método de envío elegido (Odoo sale.order.carrier_id, que el módulo
    # ``delivery`` añade a sale.order — delivery/models/sale_order.py:13).
    # E1 del retiro del espejo: el dato vivía sólo en orders.Order.
    # SET_NULL — el catálogo de envío es configuración; darlo de baja no
    # puede llevarse la venta por delante.
    carrier     = fields.Many2one(
        'delivery.ShippingMethod', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_orders',
        help_text='Método de envío elegido (Odoo sale.order.carrier_id).',
    )

    # Trazabilidad de cancelación (UC-ORD-04, UC-ORD-08 / H-ORD-001,
    # H-ADM-003). NO tienen equivalente en Odoo core —allí la cancelación es
    # ``state='cancel'`` + el hilo de ``mail.thread``—; son extensión propia
    # del proyecto, que el espejo legacy sí modelaba y el canónico no.
    admin_cancelled_by  = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='admin_cancelled_sale_orders',
        help_text='Admin que canceló. NULL si la canceló el comprador.',
    )
    cancellation_reason = fields.Text(
        blank=True, default='',
        help_text='Motivo de la cancelación (comprador o admin).',
    )
    cancelled_at        = fields.Datetime(
        null=True, blank=True,
        help_text='Momento de la cancelación. NULL si la orden no se canceló.',
    )

    # Factura de la orden (Odoo sale.order.invoice_ids, aquí 1:1). FK
    # sale→account (dirección correcta: account es la capa contable base). El
    # enlace hace idempotente action_create_invoice: una orden ya facturada no
    # emite duplicado. related_name='+' — sin accesor inverso (account limpio).
    invoice     = fields.Many2one(
        'account.AccountMove', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        help_text='Factura emitida de la orden (Odoo invoice_ids, 1:1).',
    )

    # amount_untaxed/tax/total (H-API-30) — Odoo sale/models/sale_order.py:
    # 232-234, ``store=True, compute='_compute_amounts'``. Antes eran métodos
    # Python (obligaba a un shim SQL para agregarlos); materializados como
    # columnas reales, un ``Sum('amount_total')`` agrega directo. Se
    # recalculan y persisten en ``_compute_amounts`` (más abajo), disparado
    # desde ``SaleOrderLine.save()``/``delete()`` — ver el docstring ahí. Los
    # ``tracking=5``/``=4`` de la referencia no se portan: sólo el estado
    # tiene bitácora (ver ``_track_state``).
    amount_untaxed = fields.Monetary(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Subtotal sin IVA, suma de líneas (Odoo amount_untaxed).',
    )
    amount_tax     = fields.Monetary(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='IVA de la orden, suma de líneas (Odoo amount_tax).',
    )
    amount_total   = fields.Monetary(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Total de la orden, suma de líneas (Odoo amount_total).',
    )

    objects = models.Manager()               # cross-company (L0 admin)
    scoped = CompanyScopedManager()          # L3: fail-closed por empresa activa

    class Meta:
        db_table     = 'sale_order'
        ordering     = ['-created_at']
        verbose_name = 'Orden de venta'
        verbose_name_plural = 'Órdenes de venta'

    def __str__(self):
        return self.name or f'draft:{self.cart_token or self.pk}'

    # amount_untaxed/tax/total — de sale.order._compute_amounts
    # (sale/models/sale_order.py:513): suma del desglose por línea ya redondeado.
    def _sum_lines(self, attr: str) -> Decimal:
        return sum(
            (getattr(line, attr)() for line in self.order_line.all()),
            Decimal('0.00'),
        )

    @api.depends('order_line.price_subtotal', 'order_line.price_tax',
                 'order_line.price_total')
    def _compute_amounts(self):
        """Recalcula y persiste ``amount_untaxed``/``amount_tax``/``amount_total``.

        Espeja ``sale.order._compute_amounts`` (Odoo sale/models/sale_order.py:
        513): suma el desglose ya redondeado **por línea** — ``SaleOrderLine``
        cuantiza a centavos antes de sumar (``sale_order_line.py:85-88``), no
        al final; sumar exacto y redondear al final divergiría un centavo en
        casos adversos (ver ``TestRedondeoPorLinea`` del test de paridad).

        En la referencia, ``@api.depends`` dispara este cómputo automáticamente
        cuando cambia algo de lo que depende. Django no tiene ese motor: el
        decorador de arriba es sólo documental (``orm/decorators.py``) — quien
        dispara el recálculo real es ``SaleOrderLine.save()``/``delete()``
        (mismo patrón de adaptación que ``_track`` ya documenta para el rastro
        de estado).
        """
        self.amount_untaxed = self._sum_lines('price_subtotal')
        self.amount_tax = self._sum_lines('price_tax')
        self.amount_total = self._sum_lines('price_total')
        self.save(update_fields=[
            'amount_untaxed', 'amount_tax', 'amount_total', 'updated_at'])

    # ------------------------------------------------------------------
    # Máquina de estados de venta — de sale.order (sale/models/sale_order.py):
    # action_confirm (1166), action_draft (1058), action_lock (1318),
    # action_cancel (1324). Es la transición que el checkout dispara al unificar
    # cart→order (draft → sale). Adaptación single-record de los métodos Odoo.
    # ------------------------------------------------------------------
    def _track(self, field, field_desc, field_type, old, new):
        """Deja el cambio de ``field`` en el chatter (Odoo ``tracking=True``).

        En Odoo el rastro lo dispara el ``write()`` del ORM al ver un campo con
        ``tracking=``; Django no tiene ese enganche, así que lo invoca quien
        hace la transición — mismo resultado, mecanismo adaptado (ver
        ``MailThread.message_track``). No registra nada si el valor no cambió.
        """
        if old == new:
            return None
        return self.message_track([{
            'field': field, 'field_desc': field_desc,
            'field_type': field_type, 'old': old, 'new': new,
        }])

    def _track_state(self, old):
        # tracking=5 en amount_untaxed y =4 en amount_total de la referencia
        # son prioridades de despliegue, no aplican aquí: sólo se porta el
        # rastro del estado, que es el que la bitácora del espejo cubría.
        return self._track('state', 'Estado', 'char', old, self.state)

    def action_confirm(self):
        """Confirma la cotización/carrito (draft/sent → sale)."""
        if self.state == self.STATE_CANCEL:
            raise ValidationError('No se puede confirmar una orden cancelada.')
        if not self.order_line.exists():
            raise ValidationError('No se puede confirmar una orden sin líneas.')
        previo = self.state
        if not self.name:
            self.name = _next_sale_name()
        self.state = self.STATE_SALE
        self.date_order = timezone.now()
        self.save(update_fields=['name', 'state', 'date_order', 'updated_at'])
        self._track_state(previo)
        return True

    def action_draft(self):
        """Reabre a borrador (cancel/sent → draft)."""
        if self.state in (self.STATE_CANCEL, self.STATE_SENT):
            previo = self.state
            self.state = self.STATE_DRAFT
            self.save(update_fields=['state', 'updated_at'])
            self._track_state(previo)
        return True

    def action_cancel(self):
        """Cancela la orden (Odoo action_cancel; bloqueada → error)."""
        if self.locked:
            raise ValidationError('No se puede cancelar una orden bloqueada.')
        previo = self.state
        self.state = self.STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])
        self._track_state(previo)
        return True

    def action_lock(self):
        previo = self.locked
        self.locked = True
        self.save(update_fields=['locked', 'updated_at'])
        self._track('locked', 'Bloqueada', 'boolean', previo, self.locked)
        return True

    def action_unlock(self):
        previo = self.locked
        self.locked = False
        self.save(update_fields=['locked', 'updated_at'])
        self._track('locked', 'Bloqueada', 'boolean', previo, self.locked)
        return True

    # ------------------------------------------------------------------
    # Puente O2C → factura (H-API-08 (a)). sale es dueño del enganche a
    # account (dirección de dependencia correcta: account es la capa base y no
    # importa sale). Espeja Odoo sale.order._create_invoices como acción
    # EXPLÍCITA — NO un efecto de action_confirm (auto-facturar al confirmar es
    # política config-gated tipo website_sale.automatic_invoice; se difiere).
    # ------------------------------------------------------------------
    def action_create_invoice(self):
        """Emite y postea la factura de esta orden, o devuelve la existente.

        Idempotente: si la orden ya tiene ``invoice``, la devuelve sin emitir
        un duplicado (Odoo salta órdenes ya facturadas). Requiere que la orden
        esté confirmada (``state='sale'``) y tenga empresa emisora.

        :raises UserError: si la orden no tiene empresa, no está confirmada o
            sin líneas, o a la empresa le faltan el diario/cuentas (delegado a
            ``account.services.create_invoice_from_sale_order``).
        """
        if self.invoice_id is not None:
            return self.invoice
        if self.company_id is None:
            raise UserError(_('La orden no tiene empresa asignada para facturar.'))
        move = create_invoice_from_sale_order(self, self.company)
        move.post()
        self.invoice = move
        self.save(update_fields=['invoice', 'updated_at'])
        return move
