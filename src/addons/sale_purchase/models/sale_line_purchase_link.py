"""Modelo ``SaleLinePurchaseLink`` — addon ``sale_purchase``.

Adaptación de Odoo ``sale_purchase`` (idéntico en 18 y 19): extiende
``sale.order.line`` con ``purchase_line_ids`` (One2many a ``purchase.order.line``
vía ``sale_line_id``) y, al confirmar una línea de *servicio a comprar*
(``service_to_purchase``), genera líneas/órdenes de compra
(``_purchase_service_generation``). Como Odoo inyecta ``sale_line_id`` **en**
``purchase.order.line`` — imposible cross-app en Django (DEC-SALE-01) — el enlace
vive en un **modelo relacionado** de esta app: cada ``purchase.order.line``
generada conoce su línea de venta origen a través de ``SaleLinePurchaseLink``.

Bridge ``sale`` + ``purchase``: aprovisiona la compra que una venta de servicio
origina, y mantiene la trazabilidad venta→compra (Odoo sale_line_id).
"""
import fields
import models

from addons.purchase.models import PurchaseOrder, PurchaseOrderLine
from core.models import TimeStampedModel


class SaleLinePurchaseLink(TimeStampedModel):
    """Enlace ``sale.order.line`` ↔ ``purchase.order.line`` (Odoo sale_line_id)."""

    sale_line     = fields.Many2one(
        'sale.SaleOrderLine', on_delete=models.CASCADE, related_name='purchase_links',
        help_text='Línea de venta origen (Odoo purchase.order.line.sale_line_id).',
    )
    purchase_line = models.OneToOneField(
        'purchase.PurchaseOrderLine', on_delete=models.CASCADE,
        related_name='sale_link',
        help_text='Línea de compra generada (Odoo purchase.order.line).',
    )

    class Meta:
        db_table = 'sale_line_purchase_link'
        verbose_name = 'Enlace venta↔compra de línea'
        verbose_name_plural = 'Enlaces venta↔compra de línea'

    def __str__(self) -> str:
        return f'{self.sale_line} → {self.purchase_line}'

    @classmethod
    def generate_purchase(cls, sale_line, vendor):
        """Genera una orden+línea de compra para ``sale_line`` y la enlaza.

        Réplica de Odoo ``_purchase_service_generation``: por cada línea de venta
        de servicio-a-comprar crea una ``purchase.order`` (RFQ) para el proveedor
        con una ``purchase.order.line`` que espeja producto/cantidad/precio de la
        venta, y persiste el vínculo venta→compra. Devuelve el enlace.
        """
        po = PurchaseOrder.objects.create(partner=vendor)
        pol = PurchaseOrderLine.objects.create(
            order=po, product=sale_line.product,
            name=(sale_line.name or str(sale_line.product)),
            product_qty=sale_line.product_uom_qty,
            price_unit=sale_line.price_unit,
        )
        return cls.objects.create(sale_line=sale_line, purchase_line=pol)

    @classmethod
    def purchase_line_count(cls, sale_line) -> int:
        """Conteo de líneas de compra generadas (Odoo purchase_line_count)."""
        return cls.objects.filter(sale_line=sale_line).count()
