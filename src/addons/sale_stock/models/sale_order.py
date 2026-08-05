"""Modelo ``SaleOrderDelivery`` — addon ``sale_stock``.

Adaptación fiel del módulo Odoo ``sale_stock``, que **extiende** ``sale.order``
(vía ``_inherit``) con el estado de entrega. Django no inyecta columnas entre
apps, así que la forma correcta de un módulo-extensión Odoo como app Django
separada es un **modelo relacionado** (OneToOne a ``sale.order``) que porta los
campos añadidos — el módulo ``sale_stock`` posee su propia tabla, sin tocar la de
``sale``.

``delivery_status`` (Odoo ``sale.order.delivery_status``,
sale_stock/models/sale_order.py:33) vive aquí; se alimenta del fulfillment
(``stock.picking`` en Odoo = ``logistics``/``inventory`` aquí).
"""
import fields
import models

from addons.base.models import TimeStampedModel


class SaleOrderDelivery(TimeStampedModel):
    """Extensión ``sale_stock`` de ``sale.order`` — estado de entrega."""

    # Odoo SALE_ORDER delivery_status (sale_stock/models/sale_order.py:33).
    STATUS_PENDING = 'pending'   # nada entregado
    STATUS_STARTED = 'started'   # picking creado, aún nada entregado
    STATUS_PARTIAL = 'partial'   # entregado en parte
    STATUS_FULL    = 'full'      # todo entregado
    STATUSES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_STARTED, 'Iniciada'),
        (STATUS_PARTIAL, 'Entrega parcial'),
        (STATUS_FULL,    'Entregada'),
    ]

    order          = models.OneToOneField(
        'sale.SaleOrder', on_delete=models.CASCADE, related_name='delivery',
        help_text='Orden de venta extendida (Odoo sale.order).',
    )
    delivery_status = fields.Selection(
        max_length=10, choices=STATUSES, null=True, blank=True,
        help_text='Estado de entrega (Odoo sale.order.delivery_status).',
    )
    # Del bloque Incoterm que sale_stock añade a sale.order (odoo19c:
    # sale_stock/models/sale_order.py:17-20). Se porta SOLO la mitad Char:
    # el M2O ``incoterm`` apunta a ``account.incoterms`` y esa familia no
    # está portada — regla del puente (analisis-gap-sale-contra-ambos-
    # arboles): el campo entra cuando su extremo aterrice.
    incoterm_location = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Lugar del Incoterm (Odoo sale.order.incoterm_location, '
                  'sale_stock).',
    )

    class Meta:
        db_table = 'sale_order_delivery'
        verbose_name = 'Entrega de orden de venta'
        verbose_name_plural = 'Entregas de órdenes de venta'

    def __str__(self) -> str:
        return f'{self.order} → {self.delivery_status or "sin entrega"}'

    # _compute_delivery_status (sale_stock/models/sale_order.py:91): full si toda
    # línea entregada; partial si algo; pending si nada. Lee las entregas de línea.
    def compute_status(self) -> str | None:
        line_deliveries = [
            l.delivery for l in self.order.order_line.all()
            if hasattr(l, 'delivery')
        ]
        if not line_deliveries:
            return None
        ordered = sum(ld.line.product_uom_qty for ld in line_deliveries)
        delivered = sum(ld.qty_delivered for ld in line_deliveries)
        if delivered <= 0:
            return self.STATUS_PENDING
        if delivered >= ordered:
            return self.STATUS_FULL
        return self.STATUS_PARTIAL

    def refresh_status(self) -> str | None:
        self.delivery_status = self.compute_status()
        self.save(update_fields=['delivery_status', 'updated_at'])
        return self.delivery_status
