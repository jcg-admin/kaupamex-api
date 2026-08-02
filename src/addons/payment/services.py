"""Servicios de cobro del addon ``payment``.

**Procedencia.** ``initiate_checkout_api_payment`` vivía en
``payments/services.py``; el commit ``api@3be54aa`` ("Remove payments package")
retiró la familia y el punto de entrada **no viajó** a ``payment``, dejando
colgado el import de ``payment_mercado_pago/management/commands/
mp_sandbox_charge.py:37``. Ver H-API-214.

Qué cambia respecto del original, y por qué:

- **La referencia del customer del proveedor ya no cuelga de la identidad.**
  El original leía ``user.mp_customer_id``; esa columna murió con
  ``IdentityUser`` y hoy sólo existe en ``payment.SavedCard.mp_customer_id``.
  Es además la forma de la referencia: en ``odoo19c: addons/payment`` la
  referencia del lado del proveedor vive en ``payment.token`` /
  ``payment.provider``, no en ``res.partner``. Se resuelve desde ``SavedCard``.
- ``order.partner`` es hoy un ``res.partner`` (no un ``IdentityUser``), así que
  el nombre humano se lee de ``partner.name`` — la referencia declara **un
  solo** ``name`` (``odoo19c: base/models/res_partner.py``), no
  ``first_name``/``last_name``.
"""
import json
import logging

from django.db import transaction

from addons.payment.gateways.base import BaseGateway
from addons.payment.gateways.registry import get_default_gateway
from addons.payment.models import Payment, PaymentGatewayEvent, SavedCard
from addons.sale.status_projection import STATUS_PENDING, order_status

logger = logging.getLogger(__name__)


def get_or_create_mp_customer(partner):
    """Referencia del customer del proveedor para ``partner``.

    Devuelve ``None`` si no hay partner (checkout de invitado) o si el gateway
    falla — un fallo aquí **no** bloquea el cobro, sólo pierde la asociación de
    tarjetas guardadas.
    """
    if partner is None:
        return None

    known = (SavedCard.objects
             .filter(user__partner=partner)
             .exclude(mp_customer_id='')
             .values_list('mp_customer_id', flat=True)
             .first())
    if known:
        return known

    try:
        gateway = get_default_gateway()
        return gateway.get_or_create_customer(
            email=partner.email or '',
            first_name=partner.name or '',
            last_name='',
        )
    except Exception as exc:
        logger.warning(
            'MP customer lookup/create failed for partner %s: %s',
            getattr(partner, 'pk', None), exc,
        )
        return None


def initiate_checkout_api_payment(
    order,
    token: str = '',
    installments: int = 1,
    payment_method_id: str = '',
    issuer_id: str = '',
    payer_email: str = '',
    payer_identification_type: str = '',
    payer_identification_number: str = '',
    payment_type: str = '',
    gateway: BaseGateway = None,
):
    """Inicia un pago con Checkout API (pago en sitio, sin redirección).

    ADR-018: Checkout API sobre Checkout Pro para UX transparente. A diferencia
    de Checkout Pro, la respuesta del proveedor es **síncrona**: el estado
    approved/rejected/pending se conoce de inmediato. El webhook posterior
    (DEC-V2-02) actúa como confirmación idempotente.

    :param order: ``SaleOrder`` en estado PENDING.
    :param token: token del formulario de tarjeta (caduca, un solo uso). Vacío
                  para métodos no-tarjeta (OXXO, SPEI, cajeros).
    :param installments: número de cuotas (1 = contado).
    :param payment_method_id: 'visa', 'master', 'oxxo', 'clabe'…
    :param issuer_id: banco emisor (mejora la tasa de aprobación).
    :param payer_email: email del pagador.
    :param gateway: gateway explícito; ``None`` usa el por defecto.
    :returns: ``(Payment, PaymentResult)``.
    :raises ValueError: si la orden no está en PENDING.
    :raises RuntimeError: si el gateway falla (se propaga al llamador).
    """
    _status = order_status(order)
    if _status != STATUS_PENDING:
        raise ValueError(
            f'La orden {order.name} no está en PENDING '
            f'(estado actual: {_status}).'
        )

    if gateway is None:
        gateway = get_default_gateway()

    customer_id = get_or_create_mp_customer(order.partner)

    result = gateway.create_payment(
        order=order,
        token=token,
        installments=installments,
        payment_method_id=payment_method_id,
        issuer_id=issuer_id,
        payer_email=payer_email,
        payer_identification_type=payer_identification_type,
        payer_identification_number=payer_identification_number,
        customer_id=customer_id or '',
        payment_type=payment_type,
    )

    if result.status == 'approved':
        payment_status = Payment.STATUS_APPROVED
        event_type     = PaymentGatewayEvent.EVENT_PAYMENT_APPROVED
    elif result.status == 'rejected':
        payment_status = Payment.STATUS_FAILED
        event_type     = PaymentGatewayEvent.EVENT_PAYMENT_FAILED
    else:
        # pending / in_process — PENDING permite reintento.
        payment_status = Payment.STATUS_PENDING
        event_type     = PaymentGatewayEvent.EVENT_PREFERENCE_CREATED

    with transaction.atomic():
        payment = Payment.objects.create(
            sale_order=order,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            gateway_payment_id=result.gateway_payment_id,
            mp_order_id=result.mp_order_id,
            status=payment_status,
            amount=result.amount,
            installments=result.installments,
        )
        PaymentGatewayEvent.objects.create(
            payment=payment,
            event_type=event_type,
            raw_body=json.dumps({
                'source':             'checkout_api',
                'gateway_payment_id': result.gateway_payment_id,
                'status':             result.status,
                'status_detail':      result.status_detail,
            }),
        )
        # O2C R8: el ``Payment`` APPROVED de arriba ES el eje de pago — la
        # proyección canónica deriva PAID de él; no se escribe columna espejo.

    logger.info(
        'Checkout API pago: orden=%s payment_id=%s status=%s detail=%s',
        order.name, result.gateway_payment_id,
        result.status, result.status_detail,
    )
    return payment, result
