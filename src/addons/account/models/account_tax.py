"""``account.tax`` — impuesto (Odoo ``account``).

Portación fiel de ``account_tax.py`` (Odoo 18/19). Campos núcleo: ``name``,
``amount`` (Float 16,4), ``amount_type`` (group/fixed/percent/division),
``type_tax_use`` (sale/purchase/none), ``price_include``, ``active``,
``company``. El cálculo completo (``_compute_amount`` con reparto) queda para el
nodo que consuma impuestos en facturación; aquí se porta el modelo + el cálculo
base de un impuesto simple.
"""
from decimal import Decimal

import fields
import models


class AccountTax(models.Model):
    """``account.tax`` — definición de un impuesto aplicable."""

    AMOUNT_TYPES = [
        ('group', 'Grupo de impuestos'),
        ('fixed', 'Fijo'),
        ('percent', 'Porcentaje'),
        ('division', 'Porcentaje impuesto incluido'),
    ]
    TYPE_TAX_USE = [
        ('sale', 'Ventas'),
        ('purchase', 'Compras'),
        ('none', 'Ninguno'),
    ]

    name          = fields.Char(
        max_length=255, help_text='Nombre del impuesto (Odoo name, requerido).',
    )
    amount        = fields.Monetary(
        max_digits=16, decimal_places=4, default=Decimal('0.0'),
        help_text='Monto/porcentaje del impuesto (Odoo amount).',
    )
    amount_type   = fields.Selection(
        max_length=12, choices=AMOUNT_TYPES, default='percent',
        help_text='Forma de cómputo (Odoo amount_type, requerido).',
    )
    type_tax_use  = fields.Selection(
        max_length=12, choices=TYPE_TAX_USE, default='sale',
        help_text='Uso del impuesto (Odoo type_tax_use, requerido).',
    )
    price_include = fields.Boolean(
        default=False,
        help_text='Precio con impuesto incluido (Odoo price_include).',
    )
    active        = fields.Boolean(
        default=True, help_text='Impuesto activo (Odoo active).',
    )
    company       = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='taxes',
        help_text='Empresa (Odoo company_id).',
    )

    class Meta:
        db_table = 'account_tax'
        ordering = ['name']
        verbose_name = 'Impuesto'
        verbose_name_plural = 'Impuestos'

    def __str__(self) -> str:
        return f'{self.name} ({self.amount})'

    def compute_amount(self, base_amount):
        """Impuesto de un ``base_amount`` según ``amount_type`` (Odoo
        ``_compute_amount``, casos simples fixed/percent/division).

        - fixed: monto fijo.
        - percent: ``base * amount/100``.
        - division: impuesto incluido → ``base - base/(1 + amount/100)``.
        - group: 0 (la suma la aportan los hijos; fuera de este núcleo).
        """
        base = Decimal(str(base_amount))
        amt = Decimal(str(self.amount))
        if self.amount_type == 'fixed':
            return amt
        if self.amount_type == 'percent':
            return base * amt / Decimal('100')
        if self.amount_type == 'division':
            if amt == Decimal('0'):
                return Decimal('0')
            return base - (base / (Decimal('1') + amt / Decimal('100')))
        return Decimal('0')
