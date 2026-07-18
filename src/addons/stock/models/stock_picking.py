"""Modelo ``StockPicking`` — addon ``stock``.

Adaptación fiel de Odoo ``stock.picking`` (``stock/models/stock_picking.py``,
idéntico en 18 y 19): transferencia de mercancía (albarán). Núcleo verificado en
ambas versiones — ``name``/``state`` (``draft``/``waiting``/``confirmed``/
``assigned``/``done``/``cancel``)/``location_id``/``location_dest_id`` +
``move_ids`` (One2many). ``state`` se computa de los movimientos en Odoo; aquí se
expone además la máquina de transiciones equivalente
(``action_confirm``/``action_assign``/``button_validate``/``action_cancel``).
"""
import uuid

from django.db import models

from core.models import TimeStampedModel


class StockPicking(TimeStampedModel):
    """``stock.picking`` — una transferencia (albarán)."""

    STATE_DRAFT     = 'draft'
    STATE_WAITING   = 'waiting'
    STATE_CONFIRMED = 'confirmed'
    STATE_ASSIGNED  = 'assigned'
    STATE_DONE      = 'done'
    STATE_CANCEL    = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Borrador'),
        (STATE_WAITING, 'Esperando otro movimiento'),
        (STATE_CONFIRMED, 'Esperando'),
        (STATE_ASSIGNED, 'Disponible'),
        (STATE_DONE, 'Hecho'),
        (STATE_CANCEL, 'Cancelada'),
    ]

    name             = models.CharField(
        max_length=32, blank=True, default='',
        help_text='Referencia (Odoo stock.picking.name).',
    )
    state            = models.CharField(
        max_length=16, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado (Odoo stock.picking.state).',
    )
    location         = models.ForeignKey(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pickings_out', help_text='Origen (Odoo location_id).',
    )
    location_dest    = models.ForeignKey(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='pickings_in', help_text='Destino (Odoo location_dest_id).',
    )

    class Meta:
        db_table = 'stock_picking'
        ordering = ['-created_at', '-id']
        verbose_name = 'Transferencia de inventario'
        verbose_name_plural = 'Transferencias de inventario'

    def __str__(self) -> str:
        return self.name or f'{self.state}:{self.pk}'

    def action_confirm(self):
        """Confirma la transferencia y sus movimientos (Odoo action_confirm)."""
        if not self.name:
            self.name = f'WH/{uuid.uuid4().hex[:8].upper()}'
        self.state = self.STATE_CONFIRMED
        self.save(update_fields=['name', 'state', 'updated_at'])
        for move in self.move_ids.all():
            move._action_confirm()
        return self

    def action_assign(self):
        """Reserva/asigna la disponibilidad (Odoo action_assign)."""
        self.state = self.STATE_ASSIGNED
        self.save(update_fields=['state', 'updated_at'])
        for move in self.move_ids.all():
            move._action_assign()
        return self

    def button_validate(self):
        """Valida la transferencia → hecho (Odoo button_validate)."""
        for move in self.move_ids.all():
            move._action_done()
        self.state = self.STATE_DONE
        self.save(update_fields=['state', 'updated_at'])
        return self

    def action_cancel(self):
        """Cancela la transferencia (Odoo action_cancel)."""
        self.state = self.STATE_CANCEL
        self.save(update_fields=['state', 'updated_at'])
        for move in self.move_ids.all():
            move._action_cancel()
        return self
