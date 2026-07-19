"""Modelo ``PurchaseOrder`` — addon ``purchase``.

Adaptación fiel de Odoo ``purchase.order`` (``purchase/models/purchase_order.py``,
idéntico en 18 y 19): orden de compra a un proveedor. Núcleo verificado en ambas
versiones — ``name``/``partner_id`` (proveedor)/``date_order``/``state``
(``draft``/``sent``/``purchase``/``cancel``)/``order_line``/``note`` +
``amount_untaxed``/``amount_tax``/``amount_total``. Espeja al addon ``sale``
(``SaleOrder``) para consistencia interna: mismos montos IVA-incluido (MX) y
misma máquina de estados de confirmación/cancelación.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
import fields
import models
from django.utils import timezone

from core.models import TimeStampedModel


class PurchaseOrder(TimeStampedModel):
    """``purchase.order`` — orden de compra a un proveedor."""

    STATE_DRAFT    = 'draft'
    STATE_SENT     = 'sent'
    STATE_PURCHASE = 'purchase'
    STATE_CANCEL   = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Solicitud de cotización'),
        (STATE_SENT, 'Cotización enviada'),
        (STATE_PURCHASE, 'Orden de compra'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    # Odoo purchase.order.name (default 'New' → aquí se asigna al confirmar).
    name       = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Referencia de la orden (Odoo purchase.order.name).',
    )
    # Odoo purchase.order.partner_id — proveedor (res.partner). Aquí AUTH_USER.
    partner    = fields.Many2one(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='purchase_orders', help_text='Proveedor (Odoo partner_id).',
    )
    # Odoo purchase.order.date_order.
    date_order = fields.Datetime(
        null=True, blank=True, help_text='Fecha de la orden (Odoo date_order).',
    )
    # Odoo purchase.order.state.
    state      = fields.Selection(
        max_length=16, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado (Odoo purchase.order.state).',
    )
    # Odoo purchase.order.note.
    note       = fields.Text(
        blank=True, default='', help_text='Términos y condiciones (Odoo note).',
    )

    class Meta:
        db_table = 'purchase_order'
        ordering = ['-created_at', '-id']
        verbose_name = 'Orden de compra'
        verbose_name_plural = 'Órdenes de compra'

    def __str__(self) -> str:
        return self.name or f'{self.state}:{self.pk}'

    def _sum_lines(self, attr: str) -> Decimal:
        # Odoo purchase.order._amount_all (suma de las líneas).
        return sum(
            (getattr(line, attr)() for line in self.order_line.all()),
            Decimal('0.00'),
        ).quantize(Decimal('0.01'))

    def amount_untaxed(self) -> Decimal:
        return self._sum_lines('price_subtotal')

    def amount_tax(self) -> Decimal:
        return self._sum_lines('price_tax')

    def amount_total(self) -> Decimal:
        return self._sum_lines('price_total')

    def _generate_purchase_name(self) -> str:
        # Odoo asigna la secuencia 'purchase.order' al confirmar; aquí P-<uuid>.
        import uuid
        return f'P-{uuid.uuid4().hex[:8].upper()}'

    def button_confirm(self):
        """Confirma la RFQ → orden de compra (Odoo purchase.order.button_confirm)."""
        if self.state not in (self.STATE_DRAFT, self.STATE_SENT):
            raise ValidationError('Solo una RFQ (draft/sent) puede confirmarse.')
        if not self.order_line.exists():
            raise ValidationError('No se puede confirmar una orden sin líneas.')
        if not self.name:
            self.name = self._generate_purchase_name()
        self.state = self.STATE_PURCHASE
        from django.utils import timezone
        self.date_order = self.date_order or timezone.now()
        self.save(update_fields=['name', 'state', 'date_order', 'updated_at'])
        return self

    def button_cancel(self):
        """Cancela la orden (Odoo purchase.order.button_cancel)."""
        self.state = self.STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])
        return self
