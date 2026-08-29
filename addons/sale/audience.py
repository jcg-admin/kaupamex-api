"""Resolutor de la audiencia "compradores de un producto" — lo posee ``sale``.

Inscrito en el registro de ``mail`` (T-035). Antes esta consulta vivía dentro
de ``mail/views.py``, que para armarla importaba ``sale.SaleOrderLine``.
"""
from addons.mail.audience import register_audience_resolver
from addons.mail.models import ManualNotification
from addons.sale.models import SaleOrderLine


def product_buyers(product_id=None, **_kwargs):
    """``user_id`` distintos que compraron ``product_id``.

    E2c retiro del espejo: la línea canónica existe desde el carrito (draft);
    "comprador" exige confirmación. El marcador es ``name`` — la referencia SO
    que acuña ``SaleOrder.action_confirm`` y que nada vuelve a limpiar: ni
    ``action_cancel`` ni ``action_draft`` la borran, así que una compra
    cancelada sigue contando como compra, igual que la fila espejo que
    persistía.

    **Fue ``date_order`` hasta que ese campo portó su ``default=`` de la
    fuente** (tarea #984): desde entonces todo carrito nace con fecha, así que
    el filtro por fecha no nula habría dejado pasar a cualquiera que hubiese
    puesto el producto en el carrito sin comprarlo.
    """
    if not product_id:
        return SaleOrderLine.objects.none().values_list('order__partner_id', flat=True)
    return (
        SaleOrderLine.objects
        .filter(product_id=product_id,
                order__partner__isnull=False,
                order__name__isnull=False)
        .values_list('order__partner_id', flat=True)
        .distinct()
    )


register_audience_resolver(
    ManualNotification.RecipientType.PRODUCT_BUYERS, product_buyers,
)
