"""``account.move.line`` — apunte contable (Odoo ``account``).

Portación fiel de ``account_move_line.py`` (Odoo 18/19). Campos núcleo:
``move``, ``account``, ``name``, ``debit``, ``credit``, ``balance``
(= debit - credit, Odoo ``_compute_balance``), ``display_type``, ``quantity``,
``price_unit``, ``currency``.

``full_reconcile`` y ``matching_number`` — Adaptación de Odoo
``addons/account/models/account_move_line.py`` (odoo-tools@622ddc2a,
odoo19c:). Añadidos aquí (no en el archivo original del puerto) porque la
conciliación cuelga de los apuntes: ``account.partial.reconcile`` y
``account.full.reconcile`` (``account_partial_reconcile.py``,
``account_full_reconcile.py``) necesitan un destino de FK y una columna
donde escribir el resultado del algoritmo de agrupamiento
(``AccountPartialReconcile._update_matching_number``). ``matched_debit_ids``/
``matched_credit_ids`` de la referencia son el reverso de las FK
``debit_move_id``/``credit_move_id`` de ``account.partial.reconcile``
(``related_name`` en ese archivo, sin columna propia aquí — mismo patrón que
``Many2one``/reverse FK del resto del puerto). ``amount_residual`` /
``reconciled`` (booleano derivado) quedan DEFERIDOS: dependen de
``amount_currency`` multi-moneda que este modelo no porta todavía.
"""
from decimal import Decimal

import api
import fields
import models


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

    move        = fields.Many2one(
        'account.AccountMove', on_delete=models.CASCADE, related_name='line_ids',
        help_text='Asiento al que pertenece (Odoo move_id, requerido).',
    )
    account     = fields.Many2one(
        'account.AccountAccount', on_delete=models.PROTECT, related_name='move_lines',
        null=True, blank=True,
        help_text='Cuenta contable (Odoo account_id).',
    )
    name        = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Etiqueta del apunte (Odoo name).',
    )
    debit       = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Debe (Odoo debit).',
    )
    credit      = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Haber (Odoo credit).',
    )
    balance     = fields.Monetary(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        help_text='Saldo = debe - haber (Odoo balance, computado).',
    )
    display_type = fields.Selection(
        max_length=16, choices=DISPLAY_TYPES, blank=True, default='',
        help_text='Tipo de línea (Odoo display_type).',
    )
    quantity    = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('1.0'),
        help_text='Cantidad (Odoo quantity).',
    )
    price_unit  = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0'),
        help_text='Precio unitario (Odoo price_unit).',
    )
    currency    = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='move_lines',
        help_text='Moneda (Odoo currency_id).',
    )
    full_reconcile = fields.Many2one(
        'account.AccountFullReconcile', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='reconciled_line_ids',
        help_text='Conciliación total que agrupa este apunte (Odoo '
                   'full_reconcile_id). Nulo mientras no exista match total.',
    )
    matching_number = fields.Char(
        max_length=16, blank=True, default='',
        help_text="Odoo matching_number: 'P<id>' mientras la conciliación es "
                   "parcial (id del grupo, asignado por "
                   "AccountPartialReconcile._update_matching_number); el id "
                   "de account.full.reconcile como texto cuando es total. "
                   "Vacío si el apunte no está conciliado.",
    )

    class Meta:
        db_table = 'account_move_line'
        ordering = ['move', 'id']
        verbose_name = 'Apunte contable'
        verbose_name_plural = 'Apuntes contables'

    def __str__(self) -> str:
        return f'{self.name or self.account} {self.debit}/{self.credit}'

    @api.depends('debit', 'credit')
    def _compute_balance(self):
        # Odoo _compute_balance: balance = debit - credit.
        self.balance = (self.debit or Decimal('0.00')) - (self.credit or Decimal('0.00'))

    def save(self, *args, **kwargs):
        self._compute_balance()
        return super().save(*args, **kwargs)
