"""Receptores de las señales de ``sale`` — addon ``sale_loyalty`` (T-034).

El satélite escucha; el núcleo no lo conoce. Es la traducción a Django del
``_inherit`` de la referencia, donde ``sale_loyalty`` extiende ``sale.order``
sin que ``sale`` declare dependencia hacia él.

Los registra ``SaleLoyaltyConfig.ready()``.
"""
from django.dispatch import receiver

from addons.sale.models import SaleOrder
from addons.sale.signals import (draft_discount_requested,
                                 draft_voucher_requested)
from addons.sale_loyalty.services import (draft_coupon_discount,
                                          draft_coupon_voucher)


@receiver(draft_discount_requested, sender=SaleOrder,
          dispatch_uid='sale_loyalty.draft_coupon_discount')
def contribute_voucher_discount(sender, order, subtotal, **kwargs):
    """Aporta el descuento vivo del cupón al total del draft.

    ``get_draft_totals`` suma lo que devuelvan los receptores; si no hay
    cupón aplicado, ``draft_coupon_discount`` devuelve ``0.00`` y el total
    queda igual.
    """
    return draft_coupon_discount(order, subtotal)


@receiver(draft_voucher_requested, sender=SaleOrder,
          dispatch_uid='sale_loyalty.draft_voucher')
def contribute_applied_voucher(sender, order, **kwargs):
    """Devuelve el ``Voucher`` del cupón para que el núcleo lo consuma al
    confirmar, sin que ``sale`` conozca ``SaleOrderCoupon``."""
    return draft_coupon_voucher(order)
