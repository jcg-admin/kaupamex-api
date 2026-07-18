"""``res.currency.rate`` — historial de tipos de cambio (Odoo ``base``).

Portación fiel de ``ResCurrencyRate`` (``res_currency.py`` de Odoo 18/19). Una
fila = el tipo de cambio de una moneda en una fecha. Da el control de
conversión histórica que tiene Odoo (rate por fecha + empresa) sobre Django.

Cross-app (DEC-SALE-01): ``currency`` → ``base.ResCurrency``; ``company`` →
``company.Company``.
"""
from decimal import Decimal

from django.db import models


class ResCurrencyRate(models.Model):
    """``res.currency.rate`` — tipo de cambio de una moneda en una fecha."""

    name         = models.DateField(
        help_text='Fecha del tipo de cambio (Odoo name, requerido).',
    )
    rate         = models.DecimalField(
        max_digits=24, decimal_places=12, default=Decimal('1.0'),
        help_text='Tasa por unidad de la moneda de la empresa (Odoo rate).',
    )
    company_rate = models.DecimalField(
        max_digits=24, decimal_places=12, default=Decimal('1.0'),
        help_text='Tasa vista desde la empresa (Odoo company_rate).',
    )
    currency     = models.ForeignKey(
        'base.ResCurrency', on_delete=models.CASCADE, related_name='rates',
        help_text='Moneda (Odoo currency_id).',
    )
    company      = models.ForeignKey(
        'company.Company', on_delete=models.CASCADE, related_name='currency_rates',
        null=True, blank=True,
        help_text='Empresa (Odoo company_id).',
    )

    class Meta:
        db_table = 'res_currency_rate'
        ordering = ['-name', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['currency', 'company', 'name'],
                name='unique_currency_rate_per_day',
            ),
        ]
        verbose_name = 'Tipo de cambio'
        verbose_name_plural = 'Tipos de cambio'

    def __str__(self) -> str:
        return f'{self.currency_id} @ {self.name}: {self.rate}'
