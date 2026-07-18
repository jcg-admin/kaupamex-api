"""Modelo ``SaleOrderMatrix`` — addon ``sale_product_matrix``.

Adaptación de Odoo ``sale_product_matrix``, que **extiende** ``sale.order`` con
``report_grids`` y la lógica ``_apply_grid`` — que crea/actualiza *varias*
líneas de la orden en una sola pasada desde una matriz de cantidades. Como
módulo-extensión (DEC-SALE-01), en Django es una app propia con **modelo
relacionado** (OneToOne a ``sale.SaleOrder``) para ``report_grids``, más el
método de alta masiva.

Bridge ``sale`` + ``product_matrix``: agrega en bloque líneas de la orden desde
las celdas (variante, cantidad) de la grilla.
"""
from django.db import models

from addons.sale.models import SaleOrderLine
from core.models import TimeStampedModel


class SaleOrderMatrix(TimeStampedModel):
    """Config de matriz por orden (Odoo sale.order.report_grids + _apply_grid)."""

    order        = models.OneToOneField(
        'sale.SaleOrder', on_delete=models.CASCADE, related_name='matrix',
        help_text='Orden de venta (Odoo sale.order).',
    )
    # Odoo sale.order.report_grids.
    report_grids = models.BooleanField(
        default=True, help_text='Imprimir la grilla de variantes (Odoo report_grids).',
    )

    class Meta:
        db_table = 'sale_order_matrix'
        verbose_name = 'Matriz de orden de venta'
        verbose_name_plural = 'Matrices de órdenes de venta'

    def __str__(self) -> str:
        return f'Matriz de {self.order}'

    @classmethod
    def apply(cls, order, cells):
        """Aplica ``cells`` (lista de ``(variant, qty)``) a ``order`` en bloque.

        Replica el ``_apply_grid`` de Odoo: por cada celda con ``qty > 0`` crea
        o actualiza una línea de la orden para esa variante (una línea por
        variante); ``qty <= 0`` elimina la línea de esa variante si existe. El
        ``price_unit`` sale de ``variant.effective_price()``. Devuelve las líneas
        vigentes tras aplicar.
        """
        cls.objects.get_or_create(order=order)
        touched = []
        for variant, qty in cells:
            if qty and qty > 0:
                line, _created = SaleOrderLine.objects.update_or_create(
                    order=order, variant=variant,
                    defaults={
                        'product': variant.product,
                        'name': str(variant),
                        'product_uom_qty': qty,
                        'price_unit': variant.effective_price(),
                    },
                )
                touched.append(line)
            else:
                SaleOrderLine.objects.filter(order=order, variant=variant).delete()
        return touched
