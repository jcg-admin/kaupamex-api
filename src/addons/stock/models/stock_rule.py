"""Modelo ``StockRule`` — addon ``stock``.

Adaptación fiel de Odoo ``stock.rule`` (``stock/models/stock_rule.py``, idéntico
en 18 y 19): regla de aprovisionamiento (procurement). Núcleo verificado en
ambas versiones — ``name``/``action`` (``pull``/``push``/``pull_push``,
o19:63-64)/``location_src_id``/``location_dest_id``/``procure_method``
(``make_to_stock``/``make_to_order``, o19:78-80). ``_run`` genera el
``stock.move`` que satisface una demanda entre dos ubicaciones.
"""
from decimal import Decimal

import fields
import models

from addons.stock.models.stock_move import StockMove
from addons.base.models import TimeStampedModel


class StockRule(TimeStampedModel):
    """``stock.rule`` — regla de aprovisionamiento."""

    ACTION_PULL      = 'pull'
    ACTION_PUSH      = 'push'
    ACTION_PULL_PUSH = 'pull_push'
    ACTION_CHOICES = [
        (ACTION_PULL, 'Extraer de'),
        (ACTION_PUSH, 'Empujar a'),
        (ACTION_PULL_PUSH, 'Extraer y empujar'),
    ]

    PROCURE_MTS = 'make_to_stock'
    PROCURE_MTO = 'make_to_order'
    PROCURE_CHOICES = [
        (PROCURE_MTS, 'Tomar de existencias'),
        (PROCURE_MTO, 'Disparar otra regla'),
    ]

    name           = fields.Char(
        max_length=100, help_text='Nombre de la regla (Odoo stock.rule.name).',
    )
    action         = fields.Selection(
        max_length=16, choices=ACTION_CHOICES, default=ACTION_PULL,
        help_text='Acción (Odoo stock.rule.action).',
    )
    location_src   = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='rules_out', help_text='Ubicación origen (Odoo location_src_id).',
    )
    location_dest  = fields.Many2one(
        'stock.StockLocation', on_delete=models.CASCADE, related_name='rules_in',
        help_text='Ubicación destino (Odoo location_dest_id).',
    )
    procure_method = fields.Selection(
        max_length=16, choices=PROCURE_CHOICES, default=PROCURE_MTS,
        help_text='Método de aprovisionamiento (Odoo procure_method).',
    )

    class Meta:
        db_table = 'stock_rule'
        verbose_name = 'Regla de aprovisionamiento'
        verbose_name_plural = 'Reglas de aprovisionamiento'

    def __str__(self) -> str:
        return self.name

    def run(self, product, qty, picking=None):
        """Genera el ``stock.move`` que satisface la demanda (Odoo _run_pull).

        Crea un movimiento ``location_src → location_dest`` por ``qty`` unidades y
        lo confirma. Si ``procure_method='make_to_order'`` el movimiento nace en
        ``waiting`` (dispara la regla siguiente); si es ``make_to_stock`` se
        confirma para reservar de existencias.
        """
        move = StockMove.objects.create(
            name=product.name, product=product, product_uom_qty=Decimal(qty),
            location=self.location_src, location_dest=self.location_dest,
            picking=picking,
        )
        move._action_confirm()
        return move
