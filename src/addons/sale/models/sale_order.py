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
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
import fields
import models
from django.utils import timezone

from exceptions import UserError
from tools.translate import _

from addons.account.services import create_invoice_from_sale_order
from addons.base.models import TimeStampedModel
from addons.company.models import CompanyScopedManager


def _generate_sale_name() -> str:
    """Referencia SO al confirmar (análogo a la secuencia ``sale.order``)."""
    return f'S-{str(uuid.uuid4())[:8].upper()}'


class SaleOrder(TimeStampedModel):
    """``sale.order`` — cotización/carrito (draft) → orden de venta (sale)."""

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
        'company.Company', null=True, blank=True,
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

    def amount_untaxed(self) -> Decimal:
        return self._sum_lines('price_subtotal')

    def amount_tax(self) -> Decimal:
        return self._sum_lines('price_tax')

    def amount_total(self) -> Decimal:
        return self._sum_lines('price_total')

    # ------------------------------------------------------------------
    # Máquina de estados de venta — de sale.order (sale/models/sale_order.py):
    # action_confirm (1166), action_draft (1058), action_lock (1318),
    # action_cancel (1324). Es la transición que el checkout dispara al unificar
    # cart→order (draft → sale). Adaptación single-record de los métodos Odoo.
    # ------------------------------------------------------------------
    def action_confirm(self):
        """Confirma la cotización/carrito (draft/sent → sale)."""
        if self.state == self.STATE_CANCEL:
            raise ValidationError('No se puede confirmar una orden cancelada.')
        if not self.order_line.exists():
            raise ValidationError('No se puede confirmar una orden sin líneas.')
        if not self.name:
            self.name = _generate_sale_name()
        self.state = self.STATE_SALE
        self.date_order = timezone.now()
        self.save(update_fields=['name', 'state', 'date_order', 'updated_at'])
        return True

    def action_draft(self):
        """Reabre a borrador (cancel/sent → draft)."""
        if self.state in (self.STATE_CANCEL, self.STATE_SENT):
            self.state = self.STATE_DRAFT
            self.save(update_fields=['state', 'updated_at'])
        return True

    def action_cancel(self):
        """Cancela la orden (Odoo action_cancel; bloqueada → error)."""
        if self.locked:
            raise ValidationError('No se puede cancelar una orden bloqueada.')
        self.state = self.STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])
        return True

    def action_lock(self):
        self.locked = True
        self.save(update_fields=['locked', 'updated_at'])
        return True

    def action_unlock(self):
        self.locked = False
        self.save(update_fields=['locked', 'updated_at'])
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
