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
from .models import Payment, PaymentGatewayEvent, Payment as PaymentModel, Refund
from .gateways.paypal import PayPalGateway
from django.db.models import Sum as DjSum
from apps.settings_app.models import PaymentGateway



logger = logging.getLogger('apps')


def _get_gateway(gateway_type: str = 'MERCADOPAGO') -> BaseGateway:
    """
    Retorna la instancia del gateway solicitado.
    BR-006: MP es el gateway primario.
    BR-007: PayPal es el secundario disponible desde MVP.
    """
    if gateway_type == 'PAYPAL':
        return PayPalGateway()
    return MercadoPagoGateway()


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
    gateway_type: str = 'MERCADOPAGO',
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
        gateway = _get_gateway(gateway_type)

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
            gateway=gateway_type,
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


def execute_refund(
    payment,
    amount=None,
    reason: str = '',
    initiated_by=None,
    gateway: 'BaseGateway' = None,
):
    """
    Ejecuta un reembolso sobre un Payment aprobado.
    UC-PAY-07 (FR-PAY-07.02), UC-PAY-09.

    :param payment: instancia Payment con status=APPROVED
    :param amount: Decimal o None (None = reembolso total)
    :param reason: motivo del reembolso
    :param initiated_by: User que inicia el reembolso (admin o sistema)
    :param gateway: BaseGateway opcional (None usa el gateway del pago)
    :returns: Refund creado
    :raises ValueError: si el pago no es reembolsable
    :raises RuntimeError: si el gateway falla
    """

    if payment.status != PaymentModel.STATUS_APPROVED:
        raise ValueError(
            f'El pago no es reembolsable (estado: {payment.status}). '
            f'Solo los pagos en estado APPROVED pueden reembolsarse.'
        )

    refund_amount = amount if amount is not None else payment.amount
    if refund_amount <= Decimal('0') or refund_amount > payment.amount:
        raise ValueError(
            f'El monto de reembolso ({refund_amount}) debe ser mayor que 0 '
            f'y no superar el monto del pago ({payment.amount}).'
        )

    if gateway is None:
        gateway = _get_gateway(payment.gateway)

    # Ejecutar el reembolso en el gateway
    result = gateway.refund(
        gateway_payment_id=payment.gateway_payment_id,
        amount=refund_amount,
    )

    with transaction.atomic():
        refund = Refund.objects.create(
            payment=payment,
            amount=refund_amount,
            reason=reason,
            gateway_refund_id=result.refund_id,
            # H-REF-007: FR decía PROCESSED, el modelo tiene APPROVED
            status=Refund.STATUS_APPROVED,
        )

        # Actualizar estado del Payment
        total_refunded = (
            Refund.objects.filter(
                payment=payment, status=Refund.STATUS_APPROVED
            ).aggregate(total=DjSum('amount'))['total'] or Decimal('0')
        )

        if total_refunded >= payment.amount:
            payment.status = PaymentModel.STATUS_REFUNDED
        else:
            payment.status = PaymentModel.STATUS_PARTIALLY_REFUNDED
        payment.save(update_fields=['status'])

    logging.getLogger('apps').info(
        'Reembolso ejecutado: payment=%s amount=%s refund_id=%s',
        payment.pk, refund_amount, result.refund_id,
    )
    return refund


def get_payment_status(order_number: str, user) -> dict:
    """
    Retorna el estado del pago más reciente de una orden.
    UC-PAY-05 (FR-PAY-05.02).
    RNF-SEC-003 (H-REF-006): 404 si la orden no existe O no pertenece al user.
    """
    from apps.orders.models import Order

    try:
        order = Order.objects.get(order_number=order_number, user=user)
    except Order.DoesNotExist:
        return None  # Caller convierte en 404

    payment = (
        PaymentModel.objects.filter(order=order)
        .order_by('-created_at')
        .first()
    )
    return {
        'order_number':  order.order_number,
        'order_status':  order.status,
        'payment_status': payment.status if payment else 'NO_PAYMENT',
        'gateway':        payment.gateway if payment else None,
        'amount':         str(payment.amount) if payment else None,
        'created_at':     payment.created_at if payment else None,
    }


def get_payment_history(order_number: str, user) -> list | None:
    """
    Retorna todos los pagos de una orden ordenados por -created_at.
    UC-PAY-06. RNF-SEC-003: 404 si la orden no existe O no pertenece al user.
    """
    from apps.orders.models import Order

    try:
        order = Order.objects.get(order_number=order_number, user=user)
    except Order.DoesNotExist:
        return None

    return list(
        PaymentModel.objects.filter(order=order)
        .order_by('-created_at')
        .values(
            'id', 'gateway', 'status', 'amount',
            'installments', 'preference_id', 'gateway_payment_id',
            'created_at', 'updated_at',
        )
    )


def get_retry_eligibility(order_number: str, user) -> dict | None:
    """
    Verifica si una orden es elegible para reintentar el pago.
    UC-PAY-08 (FR-PAY-08.01). H-REF-004: condición real = Order.status=PENDING.
    """
    from apps.orders.models import Order

    try:
        order = Order.objects.get(order_number=order_number, user=user)
    except Order.DoesNotExist:
        return None

    if order.status != Order.STATUS_PENDING:
        return {
            'eligible':      False,
            'reason':        f'La orden está en estado {order.status}.',
            'codigo_error':  'ORDEN_NO_REINTENTABLE',
        }

    failed_payment = (
        PaymentModel.objects.filter(
            order=order,
            status__in=[PaymentModel.STATUS_FAILED, PaymentModel.STATUS_CANCELLED],
        )
        .order_by('-created_at')
        .first()
    )

    return {
        'eligible':          True,
        'order_number':      order.order_number,
        'order_status':      order.status,
        'last_failed_gateway': failed_payment.gateway if failed_payment else None,
        'available_gateways': _get_available_gateways(),
    }


def _get_available_gateways() -> list:
    """Retorna los gateways activos configurados en PaymentGateway."""
    return list(
        PaymentGateway.objects.filter(is_active=True)
        .values_list('gateway', flat=True)
    )
