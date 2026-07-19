"""Modelo ``SaleOrderLineProduction`` — addon ``sale_mrp``.

Adaptación de Odoo ``sale_mrp`` (idéntico en 18 y 19): puentea ``sale`` + ``mrp``.
En Odoo, al confirmar una venta de un producto make-to-order con BoM, la regla de
stock genera una ``mrp.production``; y para productos *kit* (BoM ``phantom``) la
cantidad entregada de la línea de venta se calcula explotando la BoM
(``_compute_qty_delivered`` / ``_get_bom_component_qty``). Como el enganche de
Odoo vive en ``stock.move``/reglas de stock — ausentes en este stack — el bridge
se materializa como **modelo relacionado** (DEC-SALE-01) que enlaza la línea de
venta con la orden de fabricación generada y expone la explosión de kit.

Bridge ``sale`` + ``mrp``: la venta de un producto fabricado origina su MO.
"""
from decimal import Decimal

import fields
import models

from addons.mrp.models import MrpProduction
from core.models import TimeStampedModel


class SaleOrderLineProduction(TimeStampedModel):
    """Vincula una ``sale.order.line`` con su ``mrp.production`` (Odoo sale_mrp)."""

    line       = models.OneToOneField(
        'sale.SaleOrderLine', on_delete=models.CASCADE, related_name='production_link',
        help_text='Línea de venta origen (Odoo sale.order.line).',
    )
    production = fields.Many2one(
        'mrp.MrpProduction', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sale_order_lines', help_text='Orden de fabricación (Odoo mrp.production).',
    )

    class Meta:
        db_table = 'sale_order_line_production'
        verbose_name = 'Fabricación de línea de orden de venta'
        verbose_name_plural = 'Fabricaciones de líneas de orden de venta'

    def __str__(self) -> str:
        return f'{self.line} → {self.production or "sin MO"}'

    @classmethod
    def generate_production(cls, line, bom=None):
        """Genera la ``mrp.production`` para ``line`` y persiste el vínculo.

        Réplica del alta make-to-order de Odoo ``sale_mrp``: crea una orden de
        fabricación del producto de la línea por la cantidad vendida (aplicando la
        BoM del producto si existe) y la enlaza. Idempotente por línea.
        """
        bom = bom or line.product.boms.filter(active=True).order_by('sequence', 'id').first()
        mo = MrpProduction.objects.create(
            product=line.product, product_qty=Decimal(line.product_uom_qty), bom=bom,
        )
        link, _created = cls.objects.update_or_create(
            line=line, defaults={'production': mo},
        )
        return link

    @classmethod
    def explode_kit(cls, product, qty):
        """Explota la BoM ``phantom`` (kit) de ``product`` para ``qty`` unidades.

        Réplica de ``_get_bom_component_qty`` de Odoo: para un kit, devuelve la
        lista de ``(componente, cantidad_total)`` = componente.product_qty × qty.
        Si el producto no tiene BoM kit activa, devuelve ``[]``.
        """
        bom = product.boms.filter(active=True, type='phantom').order_by('sequence', 'id').first()
        if bom is None:
            return []
        factor = Decimal(qty) / (bom.product_qty or Decimal('1'))
        return [
            (bl.product, (bl.product_qty * factor).quantize(Decimal('0.01')))
            for bl in bom.bom_line_ids.all()
        ]
