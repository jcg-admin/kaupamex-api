"""Modelo ``MrpProduction`` — addon ``mrp``.

Adaptación fiel de Odoo ``mrp.production`` (``mrp/models/mrp_production.py``,
idéntico en 18 y 19): orden de fabricación. Núcleo verificado en ambas versiones
— ``name`` (default 'New')/``product``/``product_qty``/``state``
(``draft``/``confirmed``/``progress``/``done``/``cancel``) + ``bom``. La
maquinaria de movimientos de stock (``move_raw_ids``/``move_finished_ids``,
o18:175-180), órdenes de trabajo (``workorders``) y su valoración quedan
**integradas** sobre las bases ``stock`` + ``stock_account`` (el consumo de
materia prima se valúa como salida y el terminado se recibe con costo =
materia prima valuada + mano de obra). Ver ``mrp/services.py``.
"""
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
import fields
import models

from addons.stock.models.stock_move import StockMove
from addons.base.models import TimeStampedModel


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

    name        = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Referencia (Odoo mrp.production.name).',
    )
    product     = fields.Many2one(
        'catalogue.Product', on_delete=models.PROTECT, related_name='productions',
        help_text='Producto a fabricar (Odoo product_id).',
    )
    product_qty = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('1.00'),
        help_text='Cantidad a producir (Odoo product_qty).',
    )
    bom         = fields.Many2one(
        'mrp.MrpBom', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='productions', help_text='BoM aplicada (Odoo bom_id).',
    )
    state       = fields.Selection(
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

    def move_raw_ids(self):
        """Movimientos de consumo de materia prima (Odoo move_raw_ids)."""
        ids = self.production_moves.filter(role='raw').values_list('move_id', flat=True)
        return StockMove.objects.filter(id__in=list(ids))

    def move_finished_ids(self):
        """Movimientos del producto terminado (Odoo move_finished_ids)."""
        ids = self.production_moves.filter(role='finished').values_list('move_id', flat=True)
        return StockMove.objects.filter(id__in=list(ids))

    def labor_cost(self) -> Decimal:
        """Costo de mano de obra = suma de las órdenes de trabajo (Odoo)."""
        total = Decimal('0.00')
        for wo in self.workorders.all():
            total += wo.labor_cost()
        return total
