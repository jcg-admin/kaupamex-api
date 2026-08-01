"""Reacciones de ``payments`` a las señales del núcleo ``sale``.

``sale`` no puede importar a ``payments`` —``Payment`` tiene FK a
``SaleOrder``, así que la dependencia va en sentido contrario— pero cancelar
una venta pagada obliga a devolver el dinero. La señal invierte la dirección:
el núcleo emite ``order_cancelled`` sin nombrar a nadie, y el satélite que
sabe de pagos reacciona.

Es el mismo mecanismo que ``sale_stock`` usa para ``order_confirmed``, y el
análogo del ``_inherit`` de Odoo, que Django no tiene.
"""
import logging

from django.dispatch import receiver

from addons.payment.models import Payment
from addons.sale.models import SaleOrder
from addons.sale.signals import order_cancelled

from .services import execute_refund

logger = logging.getLogger('apps')


@receiver(order_cancelled, sender=SaleOrder,
          dispatch_uid='payments_refund_on_cancel')
def refund_on_cancel(sender, order, reason='', cancelled_by=None, **kwargs):
    """Reembolsa el pago aprobado de una venta que se acaba de cancelar.

    Los pagos ``MANUAL`` se conciliaron fuera de la plataforma: no hay gateway
    al que pedirle el reembolso, y pedírselo abortaría la cancelación.

    Deja propagar el ``RuntimeError`` del gateway a propósito. El receptor
    corre dentro de la transacción de ``cancel_order``, así que levantar
    revierte la cancelación completa — que es lo correcto: una orden cancelada
    y cobrada es peor que una cancelación fallida.
    """
    approved_payment = (
        order.payments.filter(status=Payment.STATUS_APPROVED)
        .exclude(gateway=Payment.GATEWAY_MANUAL)
        .order_by('-created_at').first()
    )
    if approved_payment is None:
        return

    try:
        refund = execute_refund(
            payment=approved_payment,
            amount=None,   # reembolso total
            reason=f'Cancelación de la orden {order.name}: {reason}',
            initiated_by=cancelled_by,
        )
    except RuntimeError as exc:
        logger.error('Cancelación abortada para %s — fallo del gateway: %s',
                     order.name, exc)
        raise
    logger.info('Reembolso iniciado para la orden cancelada %s — refund_id=%s',
                order.name, refund.gateway_refund_id)
