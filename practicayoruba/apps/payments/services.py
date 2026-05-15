"""
PaymentService — apps.payments
Sprint 15 — UC-PAY-01, UC-PAY-01-EXT

Orquesta la creación de preferencias, verificación y registro de pagos.
Recibe cualquier BaseGateway — desconoce el tipo concreto (Strategy Pattern).
"""
import json
import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.urls import reverse

from .gateways.base import BaseGateway
from .gateways.mercadopago import MercadoPagoGateway
from .models import Payment, PaymentGatewayEvent

logger = logging.getLogger('apps')


def _get_default_gateway() -> BaseGateway:
    """Retorna el gateway activo por defecto (BR-006: MP es el primario)."""
    return MercadoPagoGateway()


def _build_back_urls(order_number: str, base_url: str) -> dict:
    """
    Construye las URLs de retorno del gateway.
    base_url = scheme + host, ej: 'https://api.practicayoruba.mx'
    """
    return {
        'success': f'{base_url}/api/v1/payments/{order_number}/return/?status=approved',
        'failure': f'{base_url}/api/v1/payments/{order_number}/return/?status=rejected',
        'pending': f'{base_url}/api/v1/payments/{order_number}/return/?status=pending',
    }


def initiate_payment(
    order,
    request,
    installments: int = 1,
    gateway: BaseGateway = None,
) -> Payment:
    """
    Inicia el proceso de pago para una orden.
    UC-PAY-01 (FR-PAY-01.01, FR-PAY-01.02).

    1. Valida que la orden esté en PENDING.
    2. Crea la preferencia en el gateway.
    3. Persiste el Payment con status=PENDING.
    4. Registra el evento de auditoría.

    :param order: instancia Order en estado PENDING
    :param request: HttpRequest para construir las back_urls
    :param installments: número de cuotas (1 = contado, >1 = MSI)
    :param gateway: instancia de BaseGateway (None usa el default)
    :returns: Payment creado
    :raises ValueError: si la orden no está en PENDING
    :raises RuntimeError: si el gateway falla (propagado al caller)
    """
    from apps.orders.models import Order

    if order.status != Order.STATUS_PENDING:
        raise ValueError(
            f'La orden {order.order_number} no está en estado PENDING '
            f'(estado actual: {order.status}).'
        )

    if gateway is None:
        gateway = _get_default_gateway()

    base_url  = f'{request.scheme}://{request.get_host()}'
    back_urls = _build_back_urls(order.order_number, base_url)

    result = gateway.create_preference(
        order=order,
        back_urls=back_urls,
        installments=installments,
    )

    with transaction.atomic():
        payment = Payment.objects.create(
            order=order,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            preference_id=result.preference_id,
            status=Payment.STATUS_PENDING,
            amount=order.value.total,
            installments=installments,
        )
        PaymentGatewayEvent.objects.create(
            payment=payment,
            event_type=PaymentGatewayEvent.EVENT_PREFERENCE_CREATED,
            raw_body=json.dumps({
                'preference_id': result.preference_id,
                'checkout_url':  result.checkout_url,
            }),
        )

    logger.info(
        'Payment iniciado: orden=%s preference_id=%s gateway=%s cuotas=%d',
        order.order_number, result.preference_id, Payment.GATEWAY_MERCADOPAGO, installments,
    )
    return payment, result.checkout_url


def handle_gateway_return(order_number: str, mp_payment_id: str | None, status: str) -> Payment | None:
    """
    Procesa el retorno del comprador desde el gateway.
    UC-PAY-01 paso 10.

    El estado definitivo llega via webhook (Sprint 16 UC-PAY-03).
    Aquí solo actualizamos si MP confirma 'approved' en los query params.

    :param order_number: external_reference enviado en la preferencia
    :param mp_payment_id: payment_id de MP en los query params
    :param status: estado indicado por MP en query params
    :returns: Payment actualizado o None si no encontró el pago
    """
    payment = (
        Payment.objects.filter(
            order__order_number=order_number,
            status=Payment.STATUS_PENDING,
        )
        .order_by('-created_at')
        .first()
    )
    if not payment:
        logger.warning('handle_gateway_return: no se encontró Payment pendiente para %s', order_number)
        return None

    # Registrar el evento de retorno para auditoría
    PaymentGatewayEvent.objects.create(
        payment=payment,
        event_type=PaymentGatewayEvent.EVENT_WEBHOOK_RECEIVED,
        raw_body=json.dumps({
            'source':       'gateway_return',
            'mp_payment_id': mp_payment_id,
            'status':        status,
        }),
    )

    # Solo actualizar si el gateway confirma aprobado en el retorno
    if status == 'approved' and mp_payment_id:
        payment.gateway_payment_id = mp_payment_id
        payment.status             = Payment.STATUS_APPROVED
        payment.save(update_fields=['gateway_payment_id', 'status'])
        logger.info(
            'Pago aprobado en retorno: orden=%s payment_id=%s',
            order_number, mp_payment_id,
        )

    return payment


def get_installment_plans(order, gateway: BaseGateway = None) -> list:
    """
    Consulta los planes de cuotas MSI disponibles para el monto de la orden.
    UC-PAY-01-EXT (FR-PAY-01-EXT.01).
    """
    if gateway is None:
        gateway = _get_default_gateway()
    amount = order.value.total
    return gateway.get_installment_plans(amount)
