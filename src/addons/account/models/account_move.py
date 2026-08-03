"""``account.move`` — asiento contable / factura (Odoo ``account``).

Portación fiel de ``account_move.py`` (Odoo 18/19). Campos núcleo: ``name``,
``ref``, ``date``, ``state`` (draft/posted/cancel), ``move_type``
(entry/out_invoice/…), ``journal``, ``partner``, ``currency``, ``company``,
``amount_total``. Se porta la invariante de doble entrada (Odoo
``_check_balanced``): al postear, la suma de debe == suma de haber.
"""
from decimal import Decimal

import api
from django.conf import settings
import fields
import models
from exceptions import UserError
from tools.translate import _


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
    # Prefijo de secuencia por move_type (Odoo deriva el nombre de la secuencia
    # del diario; aquí un prefijo estable por tipo, único con el código de diario).
    SEQUENCE_PREFIXES = {
        'out_invoice': 'INV',
        'out_refund': 'RINV',
        'in_invoice': 'BILL',
        'in_refund': 'RBILL',
        'out_receipt': 'RCPT',
        'in_receipt': 'PRCPT',
        'entry': 'MISC',
    }

    name         = fields.Char(
        max_length=255, blank=True, default='/',
        help_text='Número del asiento (Odoo name; "/" hasta postear).',
    )
    ref          = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Referencia (Odoo ref).',
    )
    date         = fields.Date(
        help_text='Fecha contable (Odoo date, requerido).',
    )
    state        = fields.Selection(
        max_length=8, choices=STATES, default='draft',
        help_text='Estado (Odoo state).',
    )
    move_type    = fields.Selection(
        max_length=16, choices=MOVE_TYPES, default='entry',
        help_text='Tipo de asiento (Odoo move_type).',
    )
    journal      = fields.Many2one(
        'account.AccountJournal', on_delete=models.PROTECT, related_name='moves',
        help_text='Diario (Odoo journal_id, requerido).',
    )
    partner      = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_moves',
        help_text='Contacto (Odoo partner_id → res.partner ≡ party).',
    )
    currency     = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='moves',
        help_text='Moneda (Odoo currency_id).',
    )
    company      = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='moves',
        help_text='Empresa (Odoo company_id).',
    )
    amount_total = fields.Monetary(
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

    @api.constrains('line_ids')
    def _check_balanced(self):
        """Invariante de doble entrada (Odoo ``_check_balanced``): debe == haber.

        Odoo lanza ``UserError`` si el asiento no cuadra; se replica.
        """
        if not self.is_balanced():
            raise UserError(_('El asiento no está balanceado (debe ≠ haber).'))

    def _assign_sequence(self):
        """Siguiente ``name`` por (diario, move_type, año).

        Espeja Odoo ``account.move._set_next_sequence``: numeración consecutiva
        con la forma ``{prefijo}/{código-diario}/{año}/{NNNNN}``, única por diario
        y tipo. El ``name`` global es único (constraint del modelo) porque el
        código de diario forma parte del prefijo.
        """
        prefix = self.SEQUENCE_PREFIXES.get(self.move_type, 'MISC')
        base = f'{prefix}/{self.journal.code}/{self.date.year}/'
        last = (AccountMove.objects
                .filter(journal=self.journal, move_type=self.move_type,
                        name__startswith=base)
                .exclude(pk=self.pk)
                .order_by('-name').first())
        n = 1
        if last and last.name:
            try:
                n = int(last.name.rsplit('/', 1)[1]) + 1
            except (ValueError, IndexError):
                n = 1
        return f'{base}{n:05d}'

    def post(self):
        """Publica el asiento (Odoo ``_post``): exige doble entrada balanceada.

        Rechaza postear un asiento vacío o desbalanceado. Recalcula
        ``amount_total`` y, si el ``name`` sigue en ``'/'`` (borrador), asigna la
        secuencia del diario (Odoo asigna el número al postear).
        """
        if not self.line_ids.exists():
            raise UserError(_('No se puede publicar un asiento sin líneas.'))
        self._check_balanced()
        self.compute_amount_total()
        if not self.name or self.name == '/':
            self.name = self._assign_sequence()
        self.state = 'posted'
        self.save(update_fields=['name', 'state', 'amount_total'])
        return True

    def button_cancel(self):
        """Cancela el asiento (Odoo ``button_cancel``)."""
        self.state = 'cancel'
        self.save(update_fields=['state'])
        return True
