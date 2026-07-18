"""Modelo ``StockMove`` — addon ``stock``.

Adaptación fiel de Odoo ``stock.move`` (``stock/models/stock_move.py``, idéntico
en 18 y 19): movimiento de mercancía entre dos ubicaciones. Núcleo verificado en
ambas versiones — ``name``/``product_id``/``product_uom_qty`` (demanda)/
``quantity`` (hecho/reservado)/``location_id``/``location_dest_id``/``picking_id``/
``state`` (``draft``/``waiting``/``confirmed``/``assigned``/``done``/``cancel``,
o19:107-114). Incluye la **reservación** (``_action_assign``) y el encadenamiento
origen↔destino (``move_orig_ids``/``move_dest_ids``) que Odoo usa para MTO.
"""
from decimal import Decimal

from django.db import models

from addons.stock.models.stock_quant import StockQuant
from core.models import TimeStampedModel


class StockMove(TimeStampedModel):
    """``stock.move`` — un movimiento de inventario."""

    STATE_DRAFT     = 'draft'
    STATE_WAITING   = 'waiting'
    STATE_CONFIRMED = 'confirmed'
    STATE_ASSIGNED  = 'assigned'
    STATE_DONE      = 'done'
    STATE_CANCEL    = 'cancel'
    STATE_CHOICES = [
        (STATE_DRAFT, 'Nuevo'),
        (STATE_WAITING, 'Esperando otro movimiento'),
        (STATE_CONFIRMED, 'Esperando disponibilidad'),
        (STATE_ASSIGNED, 'Disponible'),
        (STATE_DONE, 'Hecho'),
        (STATE_CANCEL, 'Cancelado'),
    ]

    name            = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Descripción (Odoo stock.move.name).',
    )
    product         = models.ForeignKey(
        'catalogue.Product', on_delete=models.PROTECT, related_name='stock_moves',
        help_text='Producto (Odoo product_id).',
    )
    product_uom_qty = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad demandada (Odoo product_uom_qty).',
    )
    quantity        = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cantidad reservada/hecha (Odoo stock.move.quantity).',
    )
    location        = models.ForeignKey(
        'stock.StockLocation', on_delete=models.PROTECT, related_name='moves_out',
        help_text='Ubicación origen (Odoo location_id).',
    )
    location_dest   = models.ForeignKey(
        'stock.StockLocation', on_delete=models.PROTECT, related_name='moves_in',
        help_text='Ubicación destino (Odoo location_dest_id).',
    )
    picking         = models.ForeignKey(
        'stock.StockPicking', null=True, blank=True, on_delete=models.CASCADE,
        related_name='move_ids', help_text='Transferencia (Odoo picking_id).',
    )
    move_orig       = models.ManyToManyField(
        'self', symmetrical=False, blank=True, related_name='move_dest',
        help_text='Movimientos origen que abastecen a éste (Odoo move_orig_ids).',
    )
    state           = models.CharField(
        max_length=16, choices=STATE_CHOICES, default=STATE_DRAFT,
        help_text='Estado (Odoo stock.move.state).',
    )

    class Meta:
        db_table = 'stock_move'
        ordering = ['id']
        verbose_name = 'Movimiento de inventario'
        verbose_name_plural = 'Movimientos de inventario'

    def __str__(self) -> str:
        return f'{self.product} {self.product_uom_qty} [{self.state}]'

    def _action_confirm(self):
        """Confirma el movimiento (Odoo _action_confirm).

        Con orígenes pendientes → ``waiting`` (MTO); sin ellos → ``confirmed``.
        """
        if self.state in (self.STATE_DONE, self.STATE_CANCEL):
            return self
        has_pending_orig = self.move_orig.exclude(state=self.STATE_DONE).exists()
        self.state = self.STATE_WAITING if has_pending_orig else self.STATE_CONFIRMED
        self.save(update_fields=['state', 'updated_at'])
        return self

    def _action_assign(self):
        """Reserva la disponibilidad (Odoo _action_assign).

        Reserva desde el stock disponible en la ubicación origen (``StockQuant``):
        ``quantity`` = min(demanda, disponible). Si cubre la demanda → ``assigned``.
        """
        if self.state not in (self.STATE_CONFIRMED, self.STATE_WAITING, self.STATE_ASSIGNED):
            return self
        available = StockQuant.available_qty(self.product, self.location)
        self.quantity = min(self.product_uom_qty, available)
        if self.quantity >= self.product_uom_qty and self.product_uom_qty > 0:
            self.state = self.STATE_ASSIGNED
        self.save(update_fields=['quantity', 'state', 'updated_at'])
        return self

    def _action_done(self):
        """Ejecuta el movimiento (Odoo _action_done): aplica los quants."""
        if self.state == self.STATE_CANCEL:
            return self
        done_qty = self.quantity or self.product_uom_qty
        StockQuant.apply_move(self.product, self.location, self.location_dest, done_qty)
        self.quantity = done_qty
        self.state = self.STATE_DONE
        self.save(update_fields=['quantity', 'state', 'updated_at'])
        return self

    def _action_cancel(self):
        """Cancela el movimiento (Odoo _action_cancel)."""
        if self.state == self.STATE_DONE:
            return self
        self.state = self.STATE_CANCEL
        self.quantity = Decimal('0.00')
        self.save(update_fields=['state', 'quantity', 'updated_at'])
        return self
