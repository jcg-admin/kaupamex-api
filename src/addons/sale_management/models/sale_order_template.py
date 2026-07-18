"""Modelo ``SaleOrderTemplate`` — addon ``sale_management``.

Adaptación fiel de Odoo ``sale_management`` (``sale.order.template``): plantilla
de cotización reutilizable — un conjunto de líneas predefinidas para prellenar
una ``sale.order``. Es un **modelo propio** del módulo (no una extensión de
``sale.order``), por eso vive en su propia app con sus tablas.

Se portan los campos comerciales core (``name``/``active``/``sequence``/``note``/
``number_of_days``/``require_signature``/``require_payment``/``prepayment_percent``).
``mail_template_id``/``journal_id``/``digest`` quedan fuera (requieren ``mail``/
``account``/``digest``, no presentes).
"""
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class SaleOrderTemplate(TimeStampedModel):
    """``sale.order.template`` — plantilla de cotización."""

    # Odoo sale.order.template.name (sale_order_template.py:18, required).
    name              = models.CharField(
        max_length=150, help_text='Nombre de la plantilla (Odoo name).',
    )
    # Odoo active (sale_order_template.py:13).
    active            = models.BooleanField(
        default=True, help_text='Archivar sin borrar (Odoo active).',
    )
    # Odoo sequence (sale_order_template.py:20).
    sequence          = models.IntegerField(
        default=10, help_text='Orden de listado (Odoo sequence).',
    )
    # Odoo note (sale_order_template.py:19) — términos y condiciones.
    note              = models.TextField(
        blank=True, default='',
        help_text='Términos y condiciones (Odoo note).',
    )
    # Odoo number_of_days (sale_order_template.py:27) — validez de la cotización.
    number_of_days    = models.PositiveIntegerField(
        default=0,
        help_text='Días de validez de la cotización (Odoo number_of_days).',
    )
    # Odoo require_signature (sale_order_template.py:31).
    require_signature = models.BooleanField(
        default=False, help_text='Requiere firma online (Odoo require_signature).',
    )
    # Odoo require_payment (sale_order_template.py:36).
    require_payment   = models.BooleanField(
        default=False, help_text='Requiere pago online (Odoo require_payment).',
    )
    # Odoo prepayment_percent (sale_order_template.py:41) — % de anticipo.
    prepayment_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Porcentaje de anticipo (Odoo prepayment_percent).',
    )

    class Meta:
        db_table = 'sale_order_template'
        ordering = ['sequence', 'name']
        verbose_name = 'Plantilla de cotización'
        verbose_name_plural = 'Plantillas de cotización'

    def __str__(self) -> str:
        return self.name
