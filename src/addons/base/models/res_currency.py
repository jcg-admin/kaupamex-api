"""``res.currency`` — moneda ISO 4217 (Odoo ``base``).

Portación fiel de ``res_currency.py`` (Odoo 18:23-47 / 19:21-49, arquitectura
idéntica). Espina base de la adaptación de familias (SOL-096):
account/sale/pricing dependen de moneda.
"""
import math
from decimal import Decimal

from django.db import models


class ResCurrency(models.Model):
    """``res.currency`` — moneda ISO 4217 (Odoo base).

    Fiel a ``res_currency.py`` (18:23-47 / 19:21-49): ``name`` (código ISO 4217,
    3 letras), ``full_name``, ``symbol``, ``rounding`` (factor), ``decimal_places``
    (compute = ``ceil(log10(1/rounding))``, o18:41 / o19:39), ``position``
    (before/after), ``active``, ``currency_unit_label``.
    """

    POSITION_AFTER  = 'after'
    POSITION_BEFORE = 'before'
    POSITION_CHOICES = [
        (POSITION_AFTER, 'Después del importe'),
        (POSITION_BEFORE, 'Antes del importe'),
    ]

    name                = models.CharField(
        max_length=3, unique=True,
        help_text='Código de moneda ISO 4217 (Odoo res.currency.name).',
    )
    full_name           = models.CharField(
        max_length=64, blank=True, default='',
        help_text='Nombre de la moneda (Odoo full_name).',
    )
    symbol              = models.CharField(
        max_length=8,
        help_text='Signo de la moneda (Odoo symbol).',
    )
    rounding            = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal('0.01'),
        help_text='Factor de redondeo (Odoo rounding).',
    )
    decimal_places      = models.IntegerField(
        default=2,
        help_text='Decimales, computado de rounding (Odoo decimal_places).',
    )
    position            = models.CharField(
        max_length=6, choices=POSITION_CHOICES, default=POSITION_AFTER,
        help_text='Posición del símbolo (Odoo position).',
    )
    active              = models.BooleanField(
        default=True, help_text='Moneda activa (Odoo active).',
    )
    currency_unit_label = models.CharField(
        max_length=32, blank=True, default='',
        help_text='Etiqueta de la unidad (Odoo currency_unit_label).',
    )

    class Meta:
        db_table = 'res_currency'
        ordering = ['name']
        verbose_name = 'Moneda'
        verbose_name_plural = 'Monedas'

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Computa ``decimal_places`` desde ``rounding`` (Odoo _compute_decimal_places).

        o18:163-168 / o19:163-168: si ``0 < rounding <= 1`` →
        ``ceil(log10(1/rounding))``; en otro caso 0.
        """
        r = float(self.rounding or 0)
        if 0 < r <= 1:
            self.decimal_places = int(math.ceil(math.log10(1 / r)))
        else:
            self.decimal_places = 0
        return super().save(*args, **kwargs)
