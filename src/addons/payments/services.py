"""
PaymentService — addons.payments
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
from addons.payment.gateways.base import BaseGateway
from addons.payment_aps.gateway import ApsGateway
from addons.payment_authorize.gateway import AuthorizeGateway
from addons.payment_custom.gateway import CustomGateway
from addons.payment_demo.gateway import DemoGateway
from addons.payment_mercado_pago.gateway import MercadoPagoGateway
from addons.payment.models import Payment, PaymentGatewayEvent, Payment as PaymentModel, Refund
from addons.payment_paypal.gateway import PayPalGateway
from addons.payment_stripe.gateway import StripeGateway
from django.db.models import F, Sum as DjSum
from addons.settings_app.models import PaymentGateway
from addons.orders.models import Order



logger = logging.getLogger('apps')


# Registro de providers de la familia payment (patrón payment_<provider> de
# Odoo). MP es el primario (BR-006) y PayPal el secundario (BR-007); el resto
# está registrado con integración pendiente (sus operaciones fallan explícito).
_GATEWAY_REGISTRY: dict[str, type[BaseGateway]] = {
    'MERCADOPAGO': MercadoPagoGateway,
    'PAYPAL': PayPalGateway,
    'APS': ApsGateway,
    'AUTHORIZE': AuthorizeGateway,
    'CUSTOM': CustomGateway,
    'DEMO': DemoGateway,
    'STRIPE': StripeGateway,
}


def _get_gateway(gateway_type: str = 'MERCADOPAGO') -> BaseGateway:
    """
    Retorna la instancia del gateway solicitado.
    BR-006: MP es el gateway primario.
    BR-007: PayPal es el secundario disponible desde MVP.
    Tipos desconocidos caen al primario (comportamiento histórico).
    """
    return _GATEWAY_REGISTRY.get(gateway_type, MercadoPagoGateway)()


def _get_default_gateway() -> BaseGateway:
    """Retorna el gateway activo por defecto (BR-006: MP es el primario)."""
    return MercadoPagoGateway()


def _build_back_urls(order_number: str, base_url: str) -> dict:
    """
    Construye las URLs de retorno del gateway.
    base_url = scheme + host, ej: 'https://api.practicayoruba.com'
    """
    return {
        'success': f'{base_url}/api/v2/payments/{order_number}/return/?status=approved',
        'failure': f'{base_url}/api/v2/payments/{order_number}/return/?status=rejected',
        'pending': f'{base_url}/api/v2/payments/{order_number}/return/?status=pending',
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
        payment.save(update_fields=['gateway_payment_id', 'status', 'updated_at'])
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

    H-CICLO20-01: select_for_update() dentro de atomic re-lee el Payment
    antes de calcular el saldo reembolsable. Previene race condition donde
    dos admins concurrentes pasaban el chequeo de estado y emitían dos
    reembolsos al gateway para el mismo pago.

    :param payment: instancia Payment con status=APPROVED
    :param amount: Decimal o None (None = reembolso total)
    :param reason: motivo del reembolso
    :param initiated_by: User que inicia el reembolso (admin o sistema)
    :param gateway: BaseGateway opcional (None usa el gateway del pago)
    :returns: Refund creado
    :raises ValueError: si el pago no es reembolsable
    :raises RuntimeError: si el gateway falla
    """

    # H-CICLO20-01: adquirir lock sobre el Payment dentro de un bloque
    # atomic para serializar solicitudes concurrentes de reembolso.
    # La validación de estado y el cálculo de saldo reembolsable se hacen
    # sobre la instancia bloqueada para evitar doble-reembolso.
    with transaction.atomic():
        locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)

        if locked_payment.status not in (
            PaymentModel.STATUS_APPROVED,
            PaymentModel.STATUS_PARTIALLY_REFUNDED,
        ):
            raise ValueError(
                f'El pago no es reembolsable (estado: {locked_payment.status}). '
                f'Solo los pagos en estado APPROVED o PARTIALLY_REFUNDED '
                f'pueden reembolsarse.'
            )

        already_refunded = (
            Refund.objects.filter(
                payment=locked_payment, status=Refund.STATUS_APPROVED,
            ).aggregate(total=DjSum('amount'))['total'] or Decimal('0')
        )
        remaining = locked_payment.amount - already_refunded
        refund_amount = amount if amount is not None else remaining
        if refund_amount <= Decimal('0') or refund_amount > remaining:
            raise ValueError(
                f'El monto de reembolso ({refund_amount}) debe ser mayor que 0 '
                f'y no superar el saldo reembolsable ({remaining}) del pago '
                f'(total {locked_payment.amount}, ya reembolsado {already_refunded}).'
            )

        if gateway is None:
            gateway = _get_gateway(locked_payment.gateway)

        # Ejecutar el reembolso en el gateway (fuera del punto de lectura
        # pero dentro del atomic; si el gateway falla la transacción se
        # revierte y no se crea el Refund en BD).
        # Migración Orders (T-502): un pago creado por Orders (tiene
        # ``mp_order_id``) se reembolsa por el Orders API (``refund_order``), no
        # por el Payments API legacy — el ``PAY`` id no es reembolsable por
        # ``/v1/payments`` en un pago Orders. Los pagos legacy (sin
        # ``mp_order_id``) y otros gateways siguen por ``refund``.
        if getattr(locked_payment, 'mp_order_id', '') and hasattr(gateway, 'refund_order'):
            result = gateway.refund_order(
                mp_order_id=locked_payment.mp_order_id,
                payment_id=locked_payment.gateway_payment_id,
                amount=refund_amount,
            )
        else:
            result = gateway.refund(
                gateway_payment_id=locked_payment.gateway_payment_id,
                amount=refund_amount,
            )

        refund = Refund.objects.create(
            payment=locked_payment,
            amount=refund_amount,
            reason=reason,
            gateway_refund_id=result.refund_id,
            # H-REF-007: FR decía PROCESSED, el modelo tiene APPROVED
            status=Refund.STATUS_APPROVED,
        )

        # Actualizar estado del Payment
        total_refunded = (
            Refund.objects.filter(
                payment=locked_payment, status=Refund.STATUS_APPROVED
            ).aggregate(total=DjSum('amount'))['total'] or Decimal('0')
        )

        if total_refunded >= locked_payment.amount:
            locked_payment.status = PaymentModel.STATUS_REFUNDED
        else:
            locked_payment.status = PaymentModel.STATUS_PARTIALLY_REFUNDED
        locked_payment.save(update_fields=['status', 'updated_at'])
        # UC-NOT-05: la notificacion es disparada automaticamente por la
        # signal _refund_created (notifications/signals.py) al hacer
        # Refund.objects.create(..., status=STATUS_APPROVED) arriba.
        # Llamarla aqui ademas causaba doble envio. Bug detectado en ciclo 43.

    logging.getLogger('apps').info(
        'Reembolso ejecutado: payment=%s amount=%s refund_id=%s',
        locked_payment.pk, refund_amount, result.refund_id,
    )
    return refund


def get_payment_status(order_number: str, user) -> dict:
    """
    Retorna el estado del pago más reciente de una orden.
    UC-PAY-05 (FR-PAY-05.02).
    RNF-SEC-003 (H-REF-006): 404 si la orden no existe O no pertenece al user.
    """

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

    try:
        order = Order.objects.get(order_number=order_number, user=user)
    except Order.DoesNotExist:
        return None

    # H-CICLO46-03: order_number field (documented in PaymentSerializer) was
    # missing from the .values() projection.  The frontend reads each
    # payment's order reference for display; returning it avoids the caller
    # having to derive it from the URL parameter.
    return list(
        PaymentModel.objects.filter(order=order)
        .annotate(order_number=F('order__order_number'))
        .order_by('-created_at')
        .values(
            'id', 'gateway', 'status', 'amount',
            'installments', 'preference_id', 'gateway_payment_id',
            'created_at', 'updated_at', 'order_number',
        )
    )


def get_retry_eligibility(order_number: str, user) -> dict | None:
    """
    Verifica si una orden es elegible para reintentar el pago.
    UC-PAY-08 (FR-PAY-08.01). H-REF-004: condición real = Order.status=PENDING.
    """

    try:
        order = Order.objects.get(order_number=order_number, user=user)
    except Order.DoesNotExist:
        return None

    if order.status != Order.STATUS_PENDING:
        return {
            'eligible':      False,
            'reason':        f'La orden está en estado {order.status}.',
            'codigo_error':  'ORDER_NOT_RETRYABLE',
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


def get_mp_public_key() -> str:
    """
    Retorna la public_key de MercadoPago para el frontend.
    BR-009: solo la public_key puede ir al frontend; el access_token nunca.
    """
    try:
        gateway = PaymentGateway.objects.get(
            gateway=PaymentGateway.GATEWAY_MERCADOPAGO,
            is_active=True,
        )
        creds      = gateway.get_credentials()
        public_key = creds.get('public_key', '')
        if not public_key:
            raise ValueError(
                'public_key no configurada en PaymentGateway MERCADOPAGO. '
                'Agrega public_key en UC-CFG-01.'
            )
        return public_key
    except PaymentGateway.DoesNotExist:
        raise ValueError('No existe un PaymentGateway activo para MERCADOPAGO.')


def get_or_create_mp_customer(user):
    """
    Obtiene o crea el customer de MercadoPago para el user dado.

    - Retorna None si user es None (guest checkout).
    - Retorna el mp_customer_id cacheado en user si ya existe.
    - Llama al gateway para crear/buscar el customer, guarda el ID en
      user.mp_customer_id y lo retorna.
    - Atrapa cualquier excepción del gateway y retorna None (no bloquea el pago).
    """
    if user is None:
        return None
    if user.mp_customer_id:
        return user.mp_customer_id
    try:
        gateway = MercadoPagoGateway()
        customer_id = gateway.get_or_create_customer(
            email=user.email,
            first_name=user.first_name or '',
            last_name=user.last_name or '',
        )
        user.mp_customer_id = customer_id
        user.save(update_fields=['mp_customer_id'])
        return customer_id
    except Exception as exc:
        logger.warning(
            'MP customer lookup/create failed for user %s: %s',
            getattr(user, 'pk', None), exc,
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
    """
    Inicia un pago con Checkout API (pago en sitio, sin redirección).
    ADR-018: Checkout API elegido sobre Checkout Pro para UX transparente.

    A diferencia de initiate_payment() (Checkout Pro), la respuesta de MP
    es síncrona: el estado approved/rejected/pending se conoce de inmediato.
    Si el pago es aprobado, la Order se actualiza a STATUS_PAID aquí;
    el webhook posterior (DEC-V2-02) actúa como confirmación idempotente.

    :param order: instancia Order en estado PENDING
    :param token: token del CardForm de MP.js (caduca en 7 min, un solo uso).
                  Vacío para métodos no-tarjeta (OXXO, SPEI, cajeros).
    :param installments: número de cuotas (1 = contado)
    :param payment_method_id: método: 'visa', 'master', 'oxxo', 'clabe', etc.
    :param issuer_id: ID del banco emisor (mejora tasa de aprobación)
    :param payer_email: email del pagador (fallback: order.user/guest_email)
    :param payer_identification_type: tipo de doc ('CURP', 'RFC', …)
    :param payer_identification_number: número de documento
    :param gateway: BaseGateway opcional (None usa MercadoPagoGateway)
    :returns: (Payment, PaymentResult) — Payment guardado y resultado de MP
    :raises ValueError: si la orden no está en PENDING
    :raises RuntimeError: si el gateway falla (propagado al caller)
    """
    if order.status != Order.STATUS_PENDING:
        raise ValueError(
            f'La orden {order.order_number} no está en PENDING '
            f'(estado actual: {order.status}).'
        )

    if gateway is None:
        gateway = MercadoPagoGateway()

    customer_id = get_or_create_mp_customer(order.user)

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
        # pending / in_process — PENDING permite reintento
        payment_status = Payment.STATUS_PENDING
        event_type     = PaymentGatewayEvent.EVENT_PREFERENCE_CREATED

    with transaction.atomic():
        payment = Payment.objects.create(
            order=order,
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

        if result.status == 'approved':
            order.status = Order.STATUS_PAID
            order.save(update_fields=['status', 'updated_at'])

    logger.info(
        'Checkout API pago: orden=%s payment_id=%s status=%s detail=%s',
        order.order_number, result.gateway_payment_id,
        result.status, result.status_detail,
    )
    return payment, result
