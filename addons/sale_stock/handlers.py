"""Receptores de las señales de ``sale`` — addon ``sale_stock`` (T-034).

En la referencia ``sale_stock`` (``depends: sale, stock_account``) es quien
abre el seguimiento de entrega al confirmarse la venta; ``sale`` no lo
declara. Aquí ocurría al revés: el núcleo importaba ``SaleOrderDelivery``.

Los registra ``SaleStockConfig.ready()``.
"""
from django.dispatch import receiver

from addons.sale.models import SaleOrder
from addons.sale.signals import order_confirmed
from addons.sale_stock.models import SaleOrderDelivery


@receiver(order_confirmed, sender=SaleOrder,
          dispatch_uid='sale_stock.abrir_seguimiento_entrega')
def open_delivery_tracking(sender, order, **kwargs):
    """Abre el seguimiento de entrega de la orden recién confirmada."""
    SaleOrderDelivery.objects.get_or_create(
        order=order,
        defaults={'delivery_status': SaleOrderDelivery.STATUS_STARTED},
    )
