"""``account.move.line`` — apunte contable (Odoo ``account``).

Portación fiel de ``account_move_line.py`` (Odoo 18/19). Campos núcleo:
``move``, ``account``, ``name``, ``debit``, ``credit``, ``balance``
(= debit - credit, Odoo ``_compute_balance``), ``display_type``, ``quantity``,
``price_unit``, ``currency``.
"""
from decimal import Decimal

from django.db import models


class AccountMoveLine(models.Model):
    """``account.move.line`` — línea (apunte) de un asiento contable."""

    DISPLAY_TYPES = [
        ('product', 'Producto'),
        ('tax', 'Impuesto'),
        ('cogs', 'Costo de venta'),
        ('payment_term', 'Plazo de pago'),
        ('line_section', 'Sección'),
        ('line_note', 'Nota'),
        ('rounding', 'Redondeo'),
    ]

    move        = models.ForeignKey(
        'account.AccountMove', on_delete=models.CASCADE, related_name='line_ids',
        help_text='Asiento al que pertenece (Odoo move_id, requerido).',
    )
    account     = models.ForeignKey(
        'account.AccountAccount', on_delete=models.PROTECT, related_name='move_lines',
        null=True, blank=True,
        help_text='Cuenta contable (Odoo account_id).',
    )
    name        = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Etiqueta del apunte (Odoo name).',
    )
    debit       = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Debe (Odoo debit).',
    )
    credit      = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Haber (Odoo credit).',
    )
    balance     = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Saldo = debe - haber (Odoo balance, computado).',
    )
    display_type = models.CharField(
        max_length=16, choices=DISPLAY_TYPES, blank=True, default='',
        help_text='Tipo de línea (Odoo display_type).',
    )
    quantity    = models.DecimalField(
        max_digits=16, decimal_places=4, default=Decimal('1.0'),
        help_text='Cantidad (Odoo quantity).',
    )
    price_unit  = models.DecimalField(
        max_digits=16, decimal_places=4, default=Decimal('0.0'),
        help_text='Precio unitario (Odoo price_unit).',
    )
    currency    = models.ForeignKey(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='move_lines',
        help_text='Moneda (Odoo currency_id).',
    )

    class Meta:
        db_table = 'account_move_line'
        ordering = ['move', 'id']
        verbose_name = 'Apunte contable'
        verbose_name_plural = 'Apuntes contables'

    def __str__(self) -> str:
        return f'{self.name or self.account} {self.debit}/{self.credit}'

    def save(self, *args, **kwargs):
        # Odoo _compute_balance: balance = debit - credit.
        self.balance = (self.debit or Decimal('0.00')) - (self.credit or Decimal('0.00'))
        return super().save(*args, **kwargs)
