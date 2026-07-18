"""Modelo ``MrpProduction`` — addon ``mrp``.

Adaptación fiel de Odoo ``mrp.production`` (``mrp/models/mrp_production.py``,
idéntico en 18 y 19): orden de fabricación. Núcleo verificado en ambas versiones
— ``name`` (default 'New')/``product``/``product_qty``/``state``
(``draft``/``confirmed``/``progress``/``done``/``cancel``) + ``bom``. La
maquinaria de movimientos de stock (``move_raw_ids``/``move_finished_ids``),
workorders y reservación se omite (Clausula 5 — no existe en este stack).
"""
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimeStampedModel


class MrpProduction(TimeStampedModel):
    """``mrp.production`` — orden de fabricación."""

    STATE_DRAFT     = 'draft'
    STATE_CONFIRMED = 'confirmed'
    STATE_PROGRESS  = 'progress'
    STATE_DONE      = 'done'
    STATE_CANCEL    = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Borrador'),
        (STATE_CONFIRMED, 'Confirmada'),
        (STATE_PROGRESS, 'En progreso'),
        (STATE_DONE, 'Terminada'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    name        = models.CharField(
        max_length=32, blank=True, default='',
        help_text='Referencia (Odoo mrp.production.name).',
    )
    product     = models.ForeignKey(
        'catalogue.Product', on_delete=models.PROTECT, related_name='productions',
        help_text='Producto a fabricar (Odoo product_id).',
    )
    product_qty = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('1.00'),
        help_text='Cantidad a producir (Odoo product_qty).',
    )
    bom         = models.ForeignKey(
        'mrp.MrpBom', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='productions', help_text='BoM aplicada (Odoo bom_id).',
    )
    state       = models.CharField(
        max_length=16, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado (Odoo mrp.production.state).',
    )

    class Meta:
        db_table = 'mrp_production'
        ordering = ['-created_at', '-id']
        verbose_name = 'Orden de fabricación'
        verbose_name_plural = 'Órdenes de fabricación'

    def __str__(self) -> str:
        return self.name or f'{self.state}:{self.pk}'

    def action_confirm(self):
        """Confirma la orden (Odoo mrp.production.action_confirm)."""
        if self.state != self.STATE_DRAFT:
            raise ValidationError('Solo una orden en borrador puede confirmarse.')
        if not self.name:
            self.name = f'MO-{uuid.uuid4().hex[:8].upper()}'
        self.state = self.STATE_CONFIRMED
        self.save(update_fields=['name', 'state', 'updated_at'])
        return self

    def button_mark_done(self):
        """Marca la orden como terminada (Odoo button_mark_done)."""
        if self.state not in (self.STATE_CONFIRMED, self.STATE_PROGRESS):
            raise ValidationError('Solo una orden confirmada/en progreso se termina.')
        self.state = self.STATE_DONE
        self.save(update_fields=['state', 'updated_at'])
        return self

    def action_cancel(self):
        """Cancela la orden (Odoo action_cancel)."""
        if self.state == self.STATE_DONE:
            raise ValidationError('Una orden terminada no puede cancelarse.')
        self.state = self.STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])
        return self
