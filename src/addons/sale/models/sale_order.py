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
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


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
    name       = models.CharField(
        max_length=20, unique=True, null=True, blank=True, db_index=True,
        help_text='Referencia SO (Odoo sale.order.name). NULL en borrador.',
    )
    partner    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_orders',
        help_text='Cliente (Odoo partner_id). NULL en carrito anónimo.',
    )
    cart_token = models.UUIDField(
        unique=True, null=True, blank=True, db_index=True,
        help_text='Carrito anónimo — draft sin partner (paridad cart.cart_token).',
    )
    state      = models.CharField(
        max_length=10, choices=STATES, default=STATE_DRAFT, db_index=True,
    )
    date_order = models.DateTimeField(
        null=True, blank=True,
        help_text='Fecha de la orden (Odoo date_order); se fija al confirmar.',
    )
    locked     = models.BooleanField(
        default=False, help_text='Orden bloqueada, no modificable (Odoo locked).',
    )
    # Odoo sale.order.team_id (Many2one crm.team) — atribución de la orden a un
    # equipo de venta. El addon ``sale`` declara ``sales_team`` como dependencia
    # justamente para añadir este campo.
    team       = models.ForeignKey(
        'sales_team.CrmTeam', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_orders',
        help_text='Equipo de venta atribuido (Odoo sale.order.team_id).',
    )
    # Contribución de ``sale_loyalty``: cupón/promo aplicado a la orden. Odoo
    # ``sale_loyalty`` puentea ``sale`` + ``loyalty`` (programas/tarjetas/premios);
    # este e-commerce usa el addon ``voucher`` (códigos de descuento) — se integra
    # su modelo sobre el grafo ``sale.order`` (paridad con ``cart.voucher``). La
    # maquinaria de puntos/tarjetas de ``loyalty`` queda fuera de scope.
    voucher    = models.ForeignKey(
        'voucher.Voucher', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sale_orders',
        help_text='Cupón aplicado (paridad cart.voucher; = sale_loyalty coupon).',
    )

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

    # Contribución de ``sale_loyalty``: descuento del cupón sobre la orden.
    # Reutiliza ``Voucher.calculate_discount`` (voucher/models.py:154) igual que
    # ``cart.get_discount``. FREE_SHIPPING retorna 0 (descuenta en envío).
    def discount_amount(self) -> Decimal:
        if not self.voucher_id:
            return Decimal('0.00')
        return self.voucher.calculate_discount(self.amount_untaxed())

    def amount_total_after_discount(self) -> Decimal:
        return self.amount_total() - self.discount_amount()

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
