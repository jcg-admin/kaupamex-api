"""``account.move`` — asiento contable / factura (Odoo ``account``).

Portación fiel de ``account_move.py`` (Odoo 18/19). Campos núcleo: ``name``,
``ref``, ``date``, ``state`` (draft/posted/cancel), ``move_type``
(entry/out_invoice/…), ``journal``, ``partner``, ``currency``, ``company``,
``amount_total``. Se porta la invariante de doble entrada (Odoo
``_check_balanced``): al postear, la suma de debe == suma de haber.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AccountMove(models.Model):
    """``account.move`` — asiento contable (o factura si ``move_type`` != entry)."""

    STATES = [
        ('draft', 'Borrador'),
        ('posted', 'Publicado'),
        ('cancel', 'Cancelado'),
    ]
    MOVE_TYPES = [
        ('entry', 'Asiento contable'),
        ('out_invoice', 'Factura de cliente'),
        ('out_refund', 'Nota de crédito de cliente'),
        ('in_invoice', 'Factura de proveedor'),
        ('in_refund', 'Nota de crédito de proveedor'),
        ('out_receipt', 'Recibo de venta'),
        ('in_receipt', 'Recibo de compra'),
    ]

    name         = models.CharField(
        max_length=255, blank=True, default='/',
        help_text='Número del asiento (Odoo name; "/" hasta postear).',
    )
    ref          = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Referencia (Odoo ref).',
    )
    date         = models.DateField(
        help_text='Fecha contable (Odoo date, requerido).',
    )
    state        = models.CharField(
        max_length=8, choices=STATES, default='draft',
        help_text='Estado (Odoo state).',
    )
    move_type    = models.CharField(
        max_length=16, choices=MOVE_TYPES, default='entry',
        help_text='Tipo de asiento (Odoo move_type).',
    )
    journal      = models.ForeignKey(
        'account.AccountJournal', on_delete=models.PROTECT, related_name='moves',
        help_text='Diario (Odoo journal_id, requerido).',
    )
    partner      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_moves',
        help_text='Contacto (Odoo partner_id → res.partner ≡ party).',
    )
    currency     = models.ForeignKey(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='moves',
        help_text='Moneda (Odoo currency_id).',
    )
    company      = models.ForeignKey(
        'company.Company', on_delete=models.CASCADE, related_name='moves',
        help_text='Empresa (Odoo company_id).',
    )
    amount_total = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Total del asiento (Odoo amount_total, computado de líneas).',
    )

    class Meta:
        db_table = 'account_move'
        ordering = ['-date', '-id']
        verbose_name = 'Asiento contable'
        verbose_name_plural = 'Asientos contables'

    def __str__(self) -> str:
        return self.name if self.name != '/' else f'(borrador #{self.pk})'

    # -- Odoo _check_balanced + _post -------------------------------------
    def is_balanced(self):
        """Suma de debe == suma de haber (Odoo ``_check_balanced``)."""
        agg = self.line_ids.aggregate(
            d=models.Sum('debit'), c=models.Sum('credit'))
        debit = agg['d'] or Decimal('0')
        credit = agg['c'] or Decimal('0')
        return debit == credit

    def compute_amount_total(self):
        """Total = suma del debe de las líneas (Odoo amount_total simplificado)."""
        agg = self.line_ids.aggregate(d=models.Sum('debit'))
        self.amount_total = agg['d'] or Decimal('0.00')
        return self.amount_total

    def post(self):
        """Publica el asiento (Odoo ``_post``): exige doble entrada balanceada.

        Rechaza postear un asiento vacío o desbalanceado (Odoo
        ``_check_balanced``). Recalcula ``amount_total``.
        """
        if not self.line_ids.exists():
            raise ValidationError('No se puede publicar un asiento sin líneas.')
        if not self.is_balanced():
            raise ValidationError(
                'El asiento no está balanceado (debe ≠ haber).')
        self.compute_amount_total()
        self.state = 'posted'
        self.save(update_fields=['state', 'amount_total'])
        return True

    def button_cancel(self):
        """Cancela el asiento (Odoo ``button_cancel``)."""
        self.state = 'cancel'
        self.save(update_fields=['state'])
        return True
