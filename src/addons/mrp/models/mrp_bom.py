"""Modelos ``MrpBom`` + ``MrpBomLine`` — addon ``mrp``.

Adaptación fiel de Odoo ``mrp.bom`` / ``mrp.bom.line`` (``mrp/models/mrp_bom.py``,
idéntico en 18 y 19): lista de materiales (BoM) de un producto y sus componentes.
Núcleo verificado en ambas versiones — ``code``/``active``/``type``
(``normal``/``phantom`` kit)/``product``/``product_qty``/``sequence`` +
``bom_line_ids`` (One2many); línea con ``product`` (componente)/``product_qty``/
``bom``/``sequence``. Se omite el routing/operaciones/atributos de variante de
Odoo (Clausula 5 — no existen en este stack; las variantes viven en chartsize).
"""
from decimal import Decimal

import fields
import models

from addons.base.models import TimeStampedModel


class MrpBom(TimeStampedModel):
    """``mrp.bom`` — lista de materiales de un producto."""

    TYPE_NORMAL      = 'normal'
    TYPE_PHANTOM     = 'phantom'
    TYPE_SUBCONTRACT = 'subcontract'
    TYPE_CHOICES = [
        (TYPE_NORMAL, 'Fabricar este producto'),
        (TYPE_PHANTOM, 'Kit'),
        # Odoo mrp_subcontracting selection_add=[('subcontract','Subcontracting')].
        (TYPE_SUBCONTRACT, 'Subcontratación'),
    ]

    code        = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Referencia de la BoM (Odoo mrp.bom.code).',
    )
    active      = fields.Boolean(
        default=True, help_text='BoM activa (Odoo active).',
    )
    type        = fields.Selection(
        max_length=16, choices=TYPE_CHOICES, default=TYPE_NORMAL,
        help_text='Tipo de BoM: normal|phantom/kit (Odoo mrp.bom.type).',
    )
    product     = fields.Many2one(
        'catalogue.Product', on_delete=models.CASCADE, related_name='boms',
        help_text='Producto fabricado (Odoo product_id/product_tmpl_id).',
    )
    product_qty = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('1.00'),
        help_text='Cantidad producida por la BoM (Odoo product_qty).',
    )
    sequence    = fields.Integer(
        default=0, help_text='Orden (Odoo sequence).',
    )

    class Meta:
        db_table = 'mrp_bom'
        ordering = ['sequence', 'id']
        verbose_name = 'Lista de materiales'
        verbose_name_plural = 'Listas de materiales'

    def __str__(self) -> str:
        return self.code or f'BoM:{self.product}'


class MrpBomLine(TimeStampedModel):
    """``mrp.bom.line`` — un componente de una BoM."""

    bom         = fields.Many2one(
        'mrp.MrpBom', on_delete=models.CASCADE, related_name='bom_line_ids',
        help_text='BoM contenedora (Odoo bom_id).',
    )
    product     = fields.Many2one(
        'catalogue.Product', on_delete=models.PROTECT, related_name='bom_lines',
        help_text='Componente (Odoo mrp.bom.line.product_id).',
    )
    product_qty = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('1.00'),
        help_text='Cantidad del componente (Odoo product_qty).',
    )
    sequence    = fields.Integer(
        default=1, help_text='Orden (Odoo sequence).',
    )

    class Meta:
        db_table = 'mrp_bom_line'
        ordering = ['sequence', 'id']
        verbose_name = 'Línea de BoM'
        verbose_name_plural = 'Líneas de BoM'

    def __str__(self) -> str:
        return f'{self.bom} — {self.product} ×{self.product_qty}'
