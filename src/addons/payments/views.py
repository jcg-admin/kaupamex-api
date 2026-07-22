"""
Views — addons.payments
Sprint 15 — UC-PAY-01, UC-PAY-01-EXT, UC-ORD-01-EXT
"""
import logging
from datetime import date
from decimal import Decimal, Decimal as Dec
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from addons.authz.permissions import HasCapability
from addons.authz.services import is_superadmin
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.db.models import F, Q, Sum
from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress, ShippingZone
from addons.orders.proxy_models import DeliveredOrder
from addons.loyalty.models import Voucher, VoucherUsage
from addons.payment.models import Payment, Payment as PaymentModel, Refund, Chargeback, SavedCard
from .serializers import (
    InitiatePaymentSerializer, MercadoPagoInitiateSerializer,
    InitiatePaymentResponseSerializer, InstallmentPlansResponseSerializer,
    PaymentSerializer, AdminPaymentSerializer, PaymentReturnSerializer,
    CheckoutEligibilitySerializer, ExpressCheckoutSerializer,
    RefundRequestSerializer, RefundSerializer, AdminRefundSerializer,
    RetryEligibilitySerializer, PaymentStatusSerializer as PSS,
    RefundRequestSerializer as RRS, ChargebackSerializer,
    CheckoutApiPaymentSerializer, CheckoutApiResponseSerializer,
    MpPublicKeySerializer, MpSaveCardSerializer, MpUpdateCardSerializer,
    ZeroDollarAuthSerializer,
)
from .services import (
    initiate_payment, handle_gateway_return, get_installment_plans,
    get_payment_status, get_payment_history, execute_refund, get_retry_eligibility,
    initiate_checkout_api_payment, get_mp_public_key, get_or_create_mp_customer,
)
from addons.mail.models.notification_emails import send_card_verification_email
from addons.payment_mercado_pago.gateway import MercadoPagoGateway
from addons.users.models import Address
from addons.base.models import SiteSettings
from addons.delivery.models import ShippingMethod
from addons.cart.models import Cart
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from django.db import transaction as db_transaction, IntegrityError
from django.utils import timezone
from addons.inventory.services import InventoryService, InsufficientStockError
from addons.orders.views import CheckoutView
from addons.orders.serializers import CheckoutSerializer, OrderSerializer
from addons.users.audit import audit_log_business
from addons.users.models import BusinessEvent
from .pdf_receipt import build_receipt_payload, render_receipt_pdf, PdfGenerationError




logger = logging.getLogger('apps')


# =============================================================================
# UC-PAY-01 — Procesar Pago con MercadoPago
# =============================================================================

class InitiatePaymentView(APIView):
    """
    POST /api/v2/payments/initiate/ (deprecated — use /mercadopago/ instead)
    Crea la preferencia de pago en el gateway y retorna la URL de checkout.
    UC-PAY-01 (FR-PAY-01.01, FR-PAY-01.02).

    El comprador debe ser redirigido a checkout_url.
    Las credenciales del gateway NUNCA aparecen en la respuesta (BR-009).
    """
    permission_classes = [IsAuthenticated]
    # H-CICLO108-05: throttle per-user to prevent repeated gateway preference
    # creation bursts. Without this limit a buyer (or a stolen token holder)
    # can hammer the endpoint, creating dozens of MercadoPago preferences for
    # the same order number and consuming gateway API quota. The select_for_update
    # lock serialises concurrent requests but does not cap total attempts.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope   = 'initiate_payment'

    @extend_schema(
        summary='[Deprecated] Iniciar pago (endpoint genérico)',
        description=(
            'DEPRECATED — usar /api/v2/payments/mercadopago/ en su lugar (OBS-U1). '
            'Crea una preferencia de pago en el gateway indicado por el campo '
            '`gateway` del body y retorna la URL de checkout. '
            'Las credenciales del gateway no aparecen en la respuesta (BR-009).'
        ),
        deprecated=True,
        request=InitiatePaymentSerializer,
        responses={
            201: InitiatePaymentResponseSerializer,
            400: OpenApiResponse(description='Orden no encontrada o no en estado PENDING.'),
            422: OpenApiResponse(description='Monto cambió desde el checkout (AMOUNT_MISMATCH).'),
            503: OpenApiResponse(description='Gateway de pago no disponible.'),
        },
        tags=['payments'],
    )
    def post(self, request):
        s = InitiatePaymentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return self._run_initiate(
            request=request,
            order_number=s.validated_data['order_number'],
            installments=s.validated_data['installments'],
            gateway_type=s.validated_data.get('gateway', 'MERCADOPAGO'),
            expected_amount=s.validated_data.get('expected_amount'),
        )

    def _run_initiate(self, request, order_number, installments, gateway_type, expected_amount):
        # DEC-BC-11 (2026-05-21): permission_classes = [IsAuthenticated]
        # garantiza request.user.is_authenticated. La rama else previa
        # (Order.objects.get sin filtro user=) era codigo muerto +
        # vector latente: si alguien cambiaba la permission a AllowAny
        # sin tocar este bloque, un comprador autenticado o invitado
        # podria iniciar pago sobre la orden de otro user (audit T-101
        # UC-PAY-01 D-09 + D-14). Codigo muerto eliminado para cerrar
        # el vector latente y mantener la invariante "solo el dueno
        # paga" como propiedad estructural.
        #
        # DEC-BC-22: select_for_update() dentro de atomic serializa requests
        # concurrentes al mismo order_number. Sin el lock, dos POST concurrentes
        # pueden ambos pasar la validacion de PENDING, crear dos preferencias en
        # el gateway y dos filas Payment — duplicando el intento de cobro.
        # La llamada al gateway (IO de red) queda dentro del atomic intencionalmente:
        # es la unica forma de garantizar la invariante "un solo Payment en vuelo
        # por orden PENDING" sin una columna de estado intermedio adicional.
        try:
            with db_transaction.atomic():
                try:
                    order = Order.objects.select_related('value').select_for_update().get(
                        order_number=order_number,
                        user=request.user,
                    )
                except Order.DoesNotExist:
                    raise ValidationError({
                        'order_number': f'Orden {order_number!r} no encontrada.',
                        'codigo_error': 'ORDER_NOT_FOUND',
                    })

                if order.status != Order.STATUS_PENDING:
                    raise ValidationError({
                        'detail': f'La orden no está en estado PENDING (estado: {order.status}).',
                        'codigo_error': 'ORDER_NOT_PAYABLE',
                    })

                # UC-PAY-01 AC-06: si el cliente envió el monto que vio en el
                # checkout y difiere del total recalculado de la orden (drift
                # de impuestos/envío entre checkout y preferencia), rechazar
                # con 422 AMOUNT_MISMATCH en lugar de cobrar un monto distinto
                # al que el comprador autorizó.
                if (expected_amount is not None
                        and expected_amount != order.value.total):
                    return Response(
                        {
                            'detail': (
                                'El monto cambió desde el checkout '
                                f'(esperado: {expected_amount}, '
                                f'actual: {order.value.total}).'
                            ),
                            'codigo_error': 'AMOUNT_MISMATCH',
                        },
                        status=422,
                    )

                payment, checkout_url = initiate_payment(
                    order=order,
                    request=request,
                    installments=installments,
                    gateway_type=gateway_type,
                )
        except ValidationError:
            raise
        except ValueError as exc:
            raise ValidationError({'detail': str(exc), 'codigo_error': 'GATEWAY_CONFIG_ERROR'})
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'GATEWAY_UNAVAILABLE'},
                status=503,
            )

        # BR-009 / RNF-SEC-001: never expose sequential internal PKs to
        # buyers.  payment.pk is an auto-increment integer that lets a
        # malicious client enumerate all payment records.  The order_number
        # (non-sequential, UUID-derived) already uniquely identifies the
        # payment context and is all the UI needs to poll /status/ or
        # /return/.  payment_id removed from the response.
        return Response(
            InitiatePaymentResponseSerializer({
                'payment_id':   None,
                'checkout_url': checkout_url,
                'order_number': order.order_number,
                'amount':       payment.amount,
                'installments': payment.installments,
            }).data,
            status=201,
        )


class MercadoPagoInitiateView(InitiatePaymentView):
    """
    POST /api/v2/payments/mercadopago/
    Crea una preferencia de pago en MercadoPago y retorna la URL de checkout.
    UC-PAY-01 (F6 Tier B, GAP-I1). El gateway queda implícito en la URL.
    """

    @extend_schema(
        summary='Iniciar pago con MercadoPago',
        description=(
            'Crea una preferencia de pago en MercadoPago y retorna la URL '
            'de checkout. El gateway está implícito en la URL — no se envía '
            'el campo `gateway` en el body. UC-PAY-01 (F6 Tier B). '
            'Las credenciales del gateway no aparecen en la respuesta (BR-009).'
        ),
        request=MercadoPagoInitiateSerializer,
        responses={
            201: InitiatePaymentResponseSerializer,
            400: OpenApiResponse(description='Orden no encontrada o no en estado PENDING.'),
            422: OpenApiResponse(description='Monto cambió desde el checkout (AMOUNT_MISMATCH).'),
            503: OpenApiResponse(description='Gateway de pago no disponible.'),
        },
        tags=['payments'],
    )
    def post(self, request):
        s = MercadoPagoInitiateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return self._run_initiate(
            request=request,
            order_number=s.validated_data['order_number'],
            installments=s.validated_data['installments'],
            gateway_type='MERCADOPAGO',
            expected_amount=s.validated_data.get('expected_amount'),
        )


class PaymentReturnView(APIView):
    """
    GET /api/v2/payments/<order_number>/return/
    Recibe el retorno del comprador desde el gateway.
    UC-PAY-01 paso 10.

    El estado definitivo llega via webhook (UC-PAY-03, Sprint 16).
    Este endpoint actualiza el Payment si MP confirma 'approved' en los query params.
    Siempre retorna HTTP 200 — el frontend debe verificar el status del pago.
    """
    permission_classes = [AllowAny]
    # H-CICLO90-02: throttle para evitar que un atacante cree PaymentGatewayEvent
    # rows ilimitados llamando este endpoint con order_numbers arbitrarios.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope   = 'payment_return'

    @extend_schema(
        summary='Retorno del gateway de pago',
        description=(
            'MP redirige el navegador del comprador aquí tras el pago. '
            'El estado definitivo llega via webhook (Sprint 16). '
            'Responde 302 hacia el storefront (SPA); el frontend '
            'verifica payment.status en la página destino.'
        ),
        parameters=[
            OpenApiParameter('order_number', str, location='path'),
            OpenApiParameter('status', str, description='Estado indicado por MP'),
            OpenApiParameter('payment_id', str, description='ID del pago en MP'),
        ],
        responses={302: None},
        tags=['payments'],
    )
    def get(self, request, order_number):
        # P-02: este endpoint recibe el NAVEGADOR del comprador (no una llamada
        # máquina-a-máquina). Antes devolvía JSON, así que "Volver a la tienda"
        # dejaba al usuario viendo un Response crudo en el host de la API. Ahora
        # actualiza el Payment si MP confirmó algo y redirige (302) al storefront.
        # Las back_urls de MP deben seguir apuntando a la API (se construyen con
        # request.get_host()), por eso el redirect ocurre aquí, no en el gateway.
        s = PaymentReturnSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)

        status = s.validated_data.get('status', 'pending')
        handle_gateway_return(
            order_number=order_number,
            mp_payment_id=s.validated_data.get('payment_id') or request.query_params.get('payment_id'),
            status=status,
        )

        base = settings.FRONTEND_URL.rstrip('/')
        if status == 'approved':
            target = f'{base}/order/{order_number}/confirmation'
        elif status == 'rejected':
            target = f'{base}/order/{order_number}/payment-failed'
        else:  # pending / in_process — página que hace polling del status real
            target = f'{base}/checkout/payment-return/{order_number}'
        return redirect(target)


# =============================================================================
# UC-PAY-10 — Generar Recibo de Compra en PDF
# =============================================================================

# Estados de orden que cuentan como "pagada" para emitir recibo (PRE-02).
_PAID_ORDER_STATUSES = frozenset({
    Order.STATUS_PAID,
    Order.STATUS_PROCESSING,
    Order.STATUS_IN_PREPARATION,
    Order.STATUS_SHIPPED,
    Order.STATUS_DELIVERED,
})


class ReceiptPdfView(APIView):
    """
    GET /api/v2/payments/<order_number>/receipt/
    Genera y descarga el recibo en PDF de una orden pagada. UC-PAY-10.

    Auth JWT; accesible por el dueño de la orden o por un admin (is_staff).
    El recibo no se persiste: se regenera idempotentemente desde los
    snapshots inmutables de la orden (BR-005).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.payments'

    @extend_schema(
        summary='Descargar recibo de compra en PDF (UC-PAY-10)',
        description=(
            'Genera el recibo en PDF de una orden pagada con libharu '
            '(ADR-017): logotipo + emisor, comprador, número de orden y fecha, '
            'tabla de ítems, totales (subtotal, IVA, envío, descuento, total) '
            'y método/estado de pago. Dueño de la orden o is_staff. '
            'Devuelve application/pdf adjunto.'
        ),
        parameters=[OpenApiParameter('order_number', str, location='path')],
        responses={
            200: OpenApiResponse(description='application/pdf (recibo).'),
            403: OpenApiResponse(description='No es dueño ni admin (FORBIDDEN).'),
            404: OpenApiResponse(description='Orden inexistente (NOT_FOUND).'),
            409: OpenApiResponse(description='Orden no pagada (ORDER_NOT_PAID).'),
            500: OpenApiResponse(description='Fallo del generador (PDF_GENERATION_FAILED).'),
        },
        tags=['payments'],
    )
    def get(self, request, order_number):
        # EX-01: orden inexistente → 404 NOT_FOUND. select_related para cargar
        # los snapshots financieros y de dirección en una sola consulta.
        order = (
            Order.objects.select_related('value', 'address')
            .filter(order_number=order_number)
            .first()
        )
        if order is None:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'NOT_FOUND'},
                status=404,
            )

        # EX-02: solicitante no dueño ni admin → 403 FORBIDDEN.
        is_owner = order.user_id is not None and order.user_id == request.user.pk
        if not (is_owner or is_superadmin(request.user)):
            return Response(
                {'detail': 'No tienes permiso sobre esta orden.',
                 'codigo_error': 'FORBIDDEN'},
                status=403,
            )

        # EX-03: orden no pagada → 409 ORDER_NOT_PAID.
        if order.status not in _PAID_ORDER_STATUSES:
            return Response(
                {'detail': 'La orden no está pagada.',
                 'codigo_error': 'ORDER_NOT_PAID'},
                status=409,
            )

        items = list(order.items.all())
        value = getattr(order, 'value', None)
        address = getattr(order, 'address', None)
        payment = (
            Payment.objects.filter(order=order, status=Payment.STATUS_APPROVED)
            .order_by('-created_at').first()
        )
        site = SiteSettings.get_current()

        payload = build_receipt_payload(
            order=order, value=value, items=items,
            address=address, payment=payment, site=site,
        )

        # EX-04: fallo del helper → 500 PDF_GENERATION_FAILED, sin PDF corrupto.
        try:
            pdf_bytes = render_receipt_pdf(payload)
        except PdfGenerationError as exc:
            logger.error('UC-PAY-10 PDF generation failed for %s: %s',
                         order_number, exc)
            return Response(
                {'detail': 'No se pudo generar el recibo.',
                 'codigo_error': 'PDF_GENERATION_FAILED'},
                status=500,
            )

        # POST-02: auditoría RECEIPT_PDF_GENERATED (actor + order + timestamp).
        audit_log_business(
            actor=request.user,
            action=BusinessEvent.ACTION_RECEIPT_PDF_GENERATED,
            request=request,
            target_type=BusinessEvent.TARGET_ORDER,
            target_id=order.pk,
            extra={'order_number': order.order_number},
        )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="recibo-{order.order_number}.pdf"'
        )
        return response


# =============================================================================
# UC-PAY-01-EXT — Cuotas MSI
# =============================================================================

class InstallmentPlansView(APIView):
    """
    GET /api/v2/payments/installments/?order_number=xxx
    Consulta los planes de cuotas MSI disponibles para el monto de la orden.
    UC-PAY-01-EXT (FR-PAY-01-EXT.01).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Planes de cuotas MSI disponibles',
        description=(
            'Consulta los planes de cuotas sin interés (MSI) disponibles '
            'en MercadoPago para el monto de la orden indicada. '
            'Solo retorna planes con interest_rate = 0.'
        ),
        parameters=[
            OpenApiParameter(
                'order_number', str, required=True,
                description='Número de la orden para calcular los planes.',
            )
        ],
        responses={
            200: InstallmentPlansResponseSerializer,
            400: OpenApiResponse(description='order_number requerido.'),
        },
        tags=['payments'],
    )
    def get(self, request):
        order_number = request.query_params.get('order_number')
        if not order_number:
            raise ValidationError({'order_number': 'Requerido.', 'codigo_error': 'ORDER_NUMBER_REQUIRED'})

        order = get_object_or_404(
            Order.objects.select_related('value'),
            order_number=order_number,
            user=request.user,
        )

        try:
            plans = get_installment_plans(order)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc), 'codigo_error': 'GATEWAY_CONFIG_ERROR'})

        return Response(
            InstallmentPlansResponseSerializer({
                'order_number': order.order_number,
                'amount':       order.value.total,
                'plans':        [
                    {
                        'installments':           p.installments,
                        'amount_per_installment': p.amount_per_installment,
                        'total_amount':           p.total_amount,
                        'interest_rate':          p.interest_rate,
                    }
                    for p in plans
                ],
            }).data
        )


# =============================================================================
# UC-ORD-01-EXT — Checkout Express
# =============================================================================

def _check_express_eligibility(user) -> dict:
    """
    Verifica si el comprador cumple las condiciones para checkout express.
    FR-ORD-01-EXT.01.
    Condiciones: autenticado + orden previa DELIVERED + dirección default.
    """
    result = {
        'express_available': False,
        'reason':            None,
        'default_address':   None,
        'default_shipping':  None,
        'estimated_total':   None,
    }

    # 1. Comprador recurrente: al menos una orden DELIVERED
    if not DeliveredOrder.objects.filter(user=user).exists():
        result['reason'] = 'Sin órdenes previas entregadas.'
        return result

    # 2. Tiene dirección predeterminada
    try:
        addr = Address.objects.get(user=user, is_default=True)
    except Address.DoesNotExist:
        result['reason'] = 'Sin dirección predeterminada.'
        return result

    # 3. Hay al menos un método de envío activo
    shipping = ShippingMethod.objects.filter(is_active=True).order_by('cost').first()
    if not shipping:
        result['reason'] = 'Sin métodos de envío disponibles.'
        return result

    result['express_available'] = True
    result['default_address'] = {
        'id':             addr.pk,
        'alias':          addr.alias,
        'recipient_name': addr.recipient_name,
        'street':         addr.street,
        'city':           addr.city,
        'state':          addr.state,
        'zip_code':       addr.zip_code,
    }
    result['default_shipping'] = {
        'id':             shipping.pk,
        'name':           shipping.name,
        'cost':           str(shipping.cost),
        'estimated_days': shipping.estimated_days,
    }
    return result


class CheckoutEligibilityView(APIView):
    """
    GET /api/v2/checkout/eligibility/
    Verifica si el comprador es elegible para checkout express.
    UC-ORD-01-EXT (FR-ORD-01-EXT.01).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Verificar elegibilidad para checkout express',
        description=(
            'Retorna express_available: true si el comprador tiene '
            'órdenes previas entregadas y dirección predeterminada. '
            'Si no es elegible, retorna reason explicando el motivo.'
        ),
        responses={200: CheckoutEligibilitySerializer},
        tags=['checkout'],
    )
    def get(self, request):
        eligibility = _check_express_eligibility(request.user)
        return Response(CheckoutEligibilitySerializer(eligibility).data)


class ExpressCheckoutView(APIView):
    """
    POST /api/v2/checkout/express/
    Crea una orden directamente con la dirección y método de envío predeterminados.
    UC-ORD-01-EXT (FR-ORD-01-EXT.02).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Checkout express',
        description=(
            'Crea una orden usando la dirección y método de envío predeterminados '
            'del comprador. Requiere ser comprador recurrente con dirección default. '
            'Retorna la orden creada lista para iniciar el pago.'
        ),
        request=ExpressCheckoutSerializer,
        responses={
            201: OpenApiResponse(description='Orden creada. Ver OrderSerializer.'),
            400: OpenApiResponse(description='No elegible para checkout express.'),
            409: OpenApiResponse(description='Stock insuficiente.'),
        },
        tags=['checkout'],
    )
    def post(self, request):
        s = ExpressCheckoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        # Verificar elegibilidad
        eligibility = _check_express_eligibility(request.user)
        if not eligibility['express_available']:
            raise ValidationError({
                'detail': eligibility['reason'],
                'codigo_error': 'NOT_ELIGIBLE_EXPRESS',
            })

        # Obtener carrito del usuario
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            raise ValidationError({'detail': 'No tienes un carrito activo.', 'codigo_error': 'EMPTY_CART'})

        if not cart.items.exists():
            raise ValidationError({'detail': 'El carrito está vacío.', 'codigo_error': 'EMPTY_CART'})

        # Reutilizar el servicio de checkout de UC-ORD-01

        addr = eligibility['default_address']
        shipping_id = eligibility['default_shipping']['id']

        checkout_data = {
            'address': {
                'recipient_name': addr['recipient_name'],
                'street':         addr['street'],
                'city':           addr['city'],
                'state':          addr['state'],
                'zip_code':       addr['zip_code'],
                'country':        'MX',
            },
            'shipping_method_id': shipping_id,
            'notes': s.validated_data.get('notes', ''),
        }

        # Crear el request interno con los datos del express
        factory = APIRequestFactory()
        inner_request = factory.post('/api/v2/checkout/', checkout_data, format='json')
        inner_request.user = request.user
        inner_request.auth = request.auth
        inner_request._request = request._request

        checkout_view = CheckoutView.as_view()
        drf_request = Request(inner_request)
        drf_request.user = request.user

        # Ejecutar el checkout directamente

        cart_items = list(cart.items.select_related('product', 'variant__product', 'variant__option').all())
        check_items = [{'product': ci.product, 'variant': ci.variant, 'quantity': ci.quantity} for ci in cart_items]

        insufficient = InventoryService.check_availability(check_items)
        if insufficient:
            return Response({'detail': 'Stock insuficiente.', 'codigo_error': 'INSUFFICIENT_STOCK', 'items': insufficient}, status=409)

        # H-CICLO21-05a: usar get_object_or_404 con is_active=True para
        # cerrar la TOCTOU race entre _check_express_eligibility() y aquí.
        # Si el método fue desactivado en ese intervalo, retorna 404 en
        # lugar de DoesNotExist sin capturar.
        settings_obj = SiteSettings.get_current()
        iva_rate = settings_obj.iva_rate
        shipping = get_object_or_404(ShippingMethod, pk=shipping_id, is_active=True)

        # H-CICLO21-05b: validar cobertura de zona de envío para la dirección
        # predeterminada (el CheckoutView lo hace; ExpressCheckout lo omitía).
        zip_code = addr.get('zip_code', '')
        if zip_code:
            all_prefixes = list(
                ShippingZone.objects.filter(is_active=True)
                .values_list('zip_code_prefix', flat=True)
            )
            if not any(zip_code.startswith(p) for p in all_prefixes):
                raise ValidationError({
                    'detail': 'El código postal de tu dirección predeterminada no está cubierto por ninguna zona de envío.',
                    'codigo_error': 'ZONE_NOT_COVERED',
                })

        subtotal_for_shipping = cart.get_subtotal() - cart.get_discount()
        shipping_cost = Dec('0.00')
        if shipping.free_threshold is None or subtotal_for_shipping < shipping.free_threshold:
            shipping_cost = shipping.cost

        try:
            with db_transaction.atomic():
                InventoryService.decrement(check_items)

                voucher_code     = cart.voucher.code if cart.voucher else ''
                voucher_discount = cart.get_discount()

                order = Order.objects.create(
                    user=request.user,
                    shipping_method=shipping,
                    voucher_code=voucher_code,
                    voucher_discount=voucher_discount,
                    notes=s.validated_data.get('notes', ''),
                )

                subtotal = Dec('0.00')
                for ci in cart_items:
                    label      = ci.variant.option.label if ci.variant else ''
                    sku        = ci.variant.sku if ci.variant else ci.product.sku
                    # H-CICLO108-06: use current_price() (live price) instead of
                    # ci.unit_price (cached price at add-to-cart time). CheckoutView
                    # already uses current_price() per H-CICLO78-04. ExpressCheckout
                    # had the same TOCTOU window: if the admin changed a price between
                    # add-to-cart and express checkout, the order snapshot would record
                    # the stale price, causing a revenue discrepancy.
                    live_price = ci.current_price()
                    item_sub   = live_price * ci.quantity
                    subtotal  += item_sub
                    OrderItem.objects.create(
                        order=order, variant=ci.variant,
                        product_name=ci.product.name,
                        variant_label=label, sku=sku,
                        unit_price=live_price, quantity=ci.quantity, subtotal=item_sub,
                    )

                net   = subtotal - voucher_discount
                tax   = (net * iva_rate / (1 + iva_rate)).quantize(Dec('0.01'))
                total = net + shipping_cost
                OrderValue.objects.create(
                    order=order, subtotal=subtotal, tax=tax,
                    shipping_cost=shipping_cost, discount=voucher_discount, total=total,
                )

                addr_data = eligibility['default_address']
                OrderAddress.objects.create(
                    order=order,
                    recipient_name=addr_data['recipient_name'],
                    street=addr_data['street'], city=addr_data['city'],
                    state=addr_data['state'], zip_code=addr_data['zip_code'],
                )

                # Increment voucher usage atomically (mirrors CheckoutView behaviour)
                if cart.voucher_id:
                    voucher_locked = (
                        Voucher.objects.select_for_update()
                        .get(pk=cart.voucher_id)
                    )
                    if (voucher_locked.max_uses is not None
                            and voucher_locked.current_uses >= voucher_locked.max_uses):
                        raise ValidationError({
                            'detail': f'Voucher {voucher_locked.code} agotado.',
                            'codigo_error': 'VOUCHER_EXHAUSTED',
                        })
                    Voucher.objects.filter(pk=cart.voucher_id).update(
                        current_uses=F('current_uses') + 1,
                        updated_at=timezone.now(),
                    )
                    VoucherUsage.objects.create(
                        user=request.user, voucher_id=cart.voucher_id)

                cart.items.all().delete()
                cart.voucher = None
                cart.save(update_fields=['voucher', 'updated_at'])

        except InsufficientStockError as exc:
            return Response({'detail': str(exc), 'codigo_error': 'INSUFFICIENT_STOCK',
                             'stock_disponible': exc.available}, status=409)
        except IntegrityError:
            # H-CICLO49-02: VoucherUsage tiene unique_together=(user, voucher).
            # En una condicion de carrera (dos requests concurrentes con el mismo
            # voucher y usuario) el segundo INSERT lanza IntegrityError desde la
            # BD. Sin este bloque except el error escala a 500. Se devuelve 409
            # alineando con el comportamiento de CheckoutView (orders/views.py).
            return Response({
                'detail': 'Este voucher ya fue utilizado en tu cuenta.',
                'codigo_error': 'VOUCHER_ALREADY_USED',
            }, status=409)

        return Response(OrderSerializer(order).data, status=201)


# =============================================================================
# Sprint 17 — UC-PAY-05, UC-PAY-06, UC-PAY-07, UC-PAY-08, UC-PAY-09
# =============================================================================

class PaymentStatusView(APIView):
    """
    GET /api/v2/payments/<order_number>/status/
    Retorna el estado del pago más reciente de la orden.
    UC-PAY-05 (FR-PAY-05.02).
    RNF-SEC-003 (H-REF-006): 404 si no existe O pertenece a otro user.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Estado del pago de una orden',
        description=(
            'Retorna el estado del pago más reciente. '
            'Si no hay ningún pago, retorna payment_status=NO_PAYMENT. '
            'RNF-SEC-003: siempre 404 si la orden no existe o no es del usuario '
            '(nunca 403 para evitar enumeración de recursos).'
        ),
        responses={
            200: OpenApiResponse(description='Estado del pago.'),
            404: OpenApiResponse(description='Orden no encontrada.'),
        },
        tags=['payments'],
    )
    def get(self, request, order_number):

        result = get_payment_status(order_number, request.user)
        if result is None:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )
        return Response(PSS(result).data)


class PaymentHistoryView(APIView):
    """
    GET /api/v2/payments/<order_number>/history/
    Retorna todos los pagos de una orden ordenados por -created_at.
    UC-PAY-06. RNF-SEC-003.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.payments'

    @extend_schema(
        summary='Historial de pagos de una orden',
        description=(
            'Lista todos los intentos de pago de la orden. '
            'Incluye pagos fallidos y aprobados. '
            'RNF-SEC-003: 404 si la orden no existe o no es del usuario.'
        ),
        responses={
            200: PaymentSerializer(many=True),
            404: OpenApiResponse(description='Orden no encontrada.'),
        },
        tags=['payments'],
    )
    def get(self, request, order_number):

        history = get_payment_history(order_number, request.user)
        if history is None:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )
        return Response(history)


class RefundView(APIView):
    """
    POST /api/v2/payments/<order_number>/refund/
    Solicita un reembolso sobre el pago aprobado de la orden.
    UC-PAY-07 (FR-PAY-07.02).
    El comprador puede solicitar el reembolso si la orden fue cancelada.
    RNF-SEC-003: 404 si la orden no existe o no es del usuario.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Solicitar reembolso',
        description=(
            'Ejecuta un reembolso total o parcial sobre el pago aprobado. '
            'amount=null → reembolso total. '
            'amount<total → reembolso parcial (Payment.status=PARTIALLY_REFUNDED). '
            'H-REF-007: Refund.status será APPROVED (no PROCESSED como en la FR).'
        ),
        request=RefundRequestSerializer,
        responses={
            201: RefundSerializer,
            400: OpenApiResponse(description='Pago no reembolsable.'),
            404: OpenApiResponse(description='Orden o pago no encontrado.'),
            503: OpenApiResponse(description='Gateway no disponible.'),
        },
        tags=['payments'],
    )
    def post(self, request, order_number):

        # RNF-SEC-003: usar filter+first, nunca get con user separado
        order = Order.objects.filter(
            order_number=order_number, user=request.user
        ).first()
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )

        payment = (
            PaymentModel.objects.filter(order=order, status=PaymentModel.STATUS_APPROVED)
            .order_by('-created_at').first()
        )
        if not payment:
            return Response(
                {'detail': 'No hay pago aprobado en esta orden.',
                 'codigo_error': 'PAYMENT_NOT_REFUNDABLE'},
                status=400,
            )

        s = RRS(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            refund = execute_refund(
                payment=payment,
                amount=s.validated_data.get('amount'),
                reason=s.validated_data.get('reason', ''),
            )
        except ValueError as exc:
            return Response({'detail': str(exc), 'codigo_error': 'PAYMENT_NOT_REFUNDABLE'},
                            status=400)
        except RuntimeError as exc:
            return Response({'detail': str(exc), 'codigo_error': 'GATEWAY_UNAVAILABLE'},
                            status=503)

        return Response(RefundSerializer(refund).data, status=201)


class RetryEligibilityView(APIView):
    """
    GET /api/v2/payments/<order_number>/retry-eligibility/
    Verifica si la orden es elegible para reintentar el pago.
    UC-PAY-08 (FR-PAY-08.01). H-REF-004: condición real = Order.status=PENDING.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Elegibilidad para reintentar pago',
        description=(
            'Verifica si la orden tiene un pago fallido y sigue en PENDING. '
            'Si eligible=true, el comprador puede usar POST /payments/initiate/ '
            'para crear un nuevo intento de pago. '
            'H-REF-004: la FR dice PENDING_PAYMENT — el estado real es PENDING.'
        ),
        responses={
            200: RetryEligibilitySerializer,
            404: OpenApiResponse(description='Orden no encontrada.'),
        },
        tags=['payments'],
    )
    def get(self, request, order_number):

        result = get_retry_eligibility(order_number, request.user)
        if result is None:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )
        # Rellenar campos opcionales para el serializer
        result.setdefault('order_number', order_number)
        result.setdefault('order_status', None)
        result.setdefault('last_failed_gateway', None)
        result.setdefault('available_gateways', [])
        result.setdefault('reason', None)
        result.setdefault('codigo_error', None)
        return Response(RetryEligibilitySerializer(result).data)


class AdminRefundView(APIView):
    """
    POST /api/v1/admin/payments/<payment_id>/refund/
    El admin inicia manualmente un reembolso sobre un pago aprobado.
    UC-PAY-09.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'payments.edit'

    @extend_schema(
        summary='Reembolso manual (admin)',
        description=(
            'El admin puede reembolsar cualquier Payment aprobado '
            'independientemente del estado de la orden. '
            'Reutiliza execute_refund() del servicio — mismo código que UC-PAY-07.'
        ),
        request=RefundRequestSerializer,
        responses={
            201: AdminRefundSerializer,
            400: OpenApiResponse(description='Pago no reembolsable.'),
            404: OpenApiResponse(description='Payment no encontrado.'),
            503: OpenApiResponse(description='Gateway no disponible.'),
        },
        tags=['payments-admin'],
    )
    def post(self, request, payment_id):

        payment = get_object_or_404(PaymentModel, pk=payment_id)

        s = RefundRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            refund = execute_refund(
                payment=payment,
                amount=s.validated_data.get('amount'),
                reason=s.validated_data.get('reason', ''),
                initiated_by=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc), 'codigo_error': 'PAYMENT_NOT_REFUNDABLE'},
                            status=400)
        except RuntimeError as exc:
            return Response({'detail': str(exc), 'codigo_error': 'GATEWAY_UNAVAILABLE'},
                            status=503)

        return Response(AdminRefundSerializer(refund).data, status=201)


# =============================================================================
# UC-PAY-11 — AdminPaymentDetailView + AdminPaymentListView
# =============================================================================

class AdminPaymentDetailView(APIView):
    """
    GET /api/v1/admin/payments/<payment_id>/
    Detalle de un pago individual para el admin.
    H-CICLO81-03: AdminPaymentListView existia pero no habia endpoint de
    detalle — el admin podia listar pagos pero no consultar uno por PK,
    impidiendo drill-down desde la lista de pagos en el panel.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'payments.view'

    @extend_schema(
        summary='Detalle de pago (admin)',
        description=(
            'Retorna el detalle completo de un Payment por su PK. '
            'No requiere filtro de propietario (admin ve todos los pagos). '
            'H-CICLO81-03: endpoint faltante — AdminPaymentListView existia '
            'sin su endpoint de detalle correspondiente. '
            'H-CICLO82-01: usa AdminPaymentSerializer (incluye order_status '
            'y user_email) en lugar del PaymentSerializer publico.'
        ),
        responses={
            200: AdminPaymentSerializer,
            404: OpenApiResponse(description='Payment no encontrado.'),
        },
        tags=['payments-admin'],
    )
    def get(self, request, payment_id):
        payment = get_object_or_404(
            PaymentModel.objects.select_related('order', 'order__user'),
            pk=payment_id,
        )
        return Response(AdminPaymentSerializer(payment).data)




class AdminPaymentListView(APIView):
    """
    GET /api/v1/admin/payments/
    Lista paginada de pagos para el admin con filtros y totales.
    UC-PAY-11.

    Filtros: ?status=, ?gateway=, ?from=YYYY-MM-DD, ?to=YYYY-MM-DD.
    Respuesta: { count, results: Payment[], totals: {approved, refunded, net} }.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'payments.view'

    @extend_schema(
        summary='Listado de transacciones de pago (admin, UC-PAY-11)',
        description=(
            'Lista paginada de todos los pagos. '
            'Filtros: status, gateway, from (YYYY-MM-DD), to (YYYY-MM-DD). '
            'Incluye totales del periodo: approved, refunded y net.'
        ),
        parameters=[
            OpenApiParameter('status',  str, required=False,
                             description='PENDING|APPROVED|FAILED|REFUNDED|PARTIALLY_REFUNDED|CANCELLED'),
            OpenApiParameter('gateway', str, required=False,
                             description='MERCADOPAGO|PAYPAL'),
            OpenApiParameter('from',    str, required=False,
                             description='Fecha inicio rango (YYYY-MM-DD).'),
            OpenApiParameter('to',      str, required=False,
                             description='Fecha fin rango (YYYY-MM-DD).'),
            OpenApiParameter('page',    int, required=False),
        ],
        responses={200: AdminPaymentSerializer(many=True)},
        tags=['payments-admin'],
    )
    def get(self, request):
        qs = (
            Payment.objects.select_related('order', 'order__user')
            .order_by('-created_at')
        )

        # --- filters ---
        status_param  = request.query_params.get('status')
        gateway_param = request.query_params.get('gateway')
        from_param    = request.query_params.get('from')
        to_param      = request.query_params.get('to')

        valid_statuses = {s[0] for s in Payment.STATUSES}
        if status_param:
            if status_param not in valid_statuses:
                raise ValidationError({
                    'status': f"'{status_param}' no es un estado válido.",
                    'codigo_error': 'INVALID_STATUS',
                    'valores_validos': list(valid_statuses),
                })
            qs = qs.filter(status=status_param)

        valid_gateways = {g[0] for g in Payment.GATEWAYS}
        if gateway_param:
            if gateway_param.upper() not in valid_gateways:
                raise ValidationError({
                    'gateway': f"'{gateway_param}' no es un gateway válido.",
                    'codigo_error': 'INVALID_GATEWAY',
                    'valores_validos': list(valid_gateways),
                })
            qs = qs.filter(gateway=gateway_param.upper())

        if from_param:
            try:
                date.fromisoformat(from_param)
            except ValueError:
                raise ValidationError({
                    'from': 'Formato de fecha inválido. Use YYYY-MM-DD.',
                    'codigo_error': 'INVALID_DATE_FORMAT',
                })
            qs = qs.filter(created_at__date__gte=from_param)

        if to_param:
            try:
                date.fromisoformat(to_param)
            except ValueError:
                raise ValidationError({
                    'to': 'Formato de fecha inválido. Use YYYY-MM-DD.',
                    'codigo_error': 'INVALID_DATE_FORMAT',
                })
            qs = qs.filter(created_at__date__lte=to_param)

        if from_param and to_param and from_param > to_param:
            raise ValidationError({
                'from': 'La fecha de inicio no puede ser posterior a la fecha de fin.',
                'codigo_error': 'INVALID_DATE_RANGE',
            })

        # --- totals over filtered queryset ---
        approved_total = qs.aggregate(
            t=Sum('amount', filter=Q(status=Payment.STATUS_APPROVED)),
        )['t'] or Decimal('0.00')
        # PAY-11: el monto reembolsado real vive en ``Refund.amount`` (uno por
        # reembolso), NO en ``Payment.amount`` — que para PARTIALLY_REFUNDED es
        # el total original del pago y sobre-cuenta el reembolso. Sumar los
        # ``Refund`` APPROVED de los pagos del queryset filtrado.
        refunded_total = Refund.objects.filter(
            status=Refund.STATUS_APPROVED,
            payment__in=qs.values('pk'),
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        totals = {
            'approved': approved_total,
            'refunded': refunded_total,
            'net':      approved_total - refunded_total,
        }

        # --- pagination ---
        paginator = PageNumberPagination()
        paginator.page_size             = 25
        paginator.page_size_query_param = 'page_size'
        paginator.max_page_size         = 100
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            response = paginator.get_paginated_response(
                AdminPaymentSerializer(page, many=True).data
            )
            response.data['totals'] = totals
            return response
        return Response({
            'count':   qs.count(),
            'results': AdminPaymentSerializer(qs, many=True).data,
            'totals':  totals,
        })


# =============================================================================
# T-16-D — AdminPaymentRefundsListView
# =============================================================================

class AdminPaymentRefundsListView(APIView):
    """
    GET /api/v2/admin/payments/<payment_id>/refunds/
    Lista todos los reembolsos de un pago específico. T-16-D.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'payments.view'

    @extend_schema(
        summary='Listado de reembolsos de un pago (admin)',
        responses={200: AdminRefundSerializer(many=True)},
        tags=['payments-admin'],
    )
    def get(self, request, payment_id):
        payment = get_object_or_404(PaymentModel, pk=payment_id)
        refunds = Refund.objects.filter(payment=payment).order_by('-created_at')
        return Response(AdminRefundSerializer(refunds, many=True).data)


# =============================================================================
# T-CAN — AdminCancelPaymentView
# =============================================================================

class AdminCancelPaymentView(APIView):
    """
    POST /api/v2/admin/payments/<payment_id>/cancel/
    El admin cancela proactivamente un pago pendiente. T-CAN.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'payments.edit'

    @extend_schema(
        summary='Cancelar pago pendiente (admin)',
        responses={
            200: OpenApiResponse(description='Pago cancelado.'),
            400: OpenApiResponse(description='El pago no está en estado cancelable.'),
            404: OpenApiResponse(description='Payment no encontrado.'),
        },
        tags=['payments-admin'],
    )
    def post(self, request, payment_id):
        payment = get_object_or_404(PaymentModel, pk=payment_id)
        if payment.status != Payment.STATUS_PENDING:
            return Response(
                {'detail': 'Solo se pueden cancelar pagos en estado PENDING.',
                 'codigo_error': 'PAYMENT_NOT_CANCELLABLE'},
                status=400,
            )
        try:
            gateway = MercadoPagoGateway()
            # Migración Orders (T-502): un pago creado por Orders (con
            # ``mp_order_id``) se cancela por el Orders API (``cancel_order``);
            # los legacy siguen por ``cancel_payment`` (/v1/payments).
            if getattr(payment, 'mp_order_id', ''):
                gateway.cancel_order(payment.mp_order_id)
            else:
                gateway.cancel_payment(payment.gateway_payment_id)
        except Exception:
            return Response(
                {'detail': 'El gateway no pudo cancelar el pago.',
                 'codigo_error': 'GATEWAY_UNAVAILABLE'},
                status=503,
            )
        payment.status = Payment.STATUS_CANCELLED
        payment.save(update_fields=['status', 'updated_at'])
        return Response(AdminPaymentSerializer(payment).data)


# =============================================================================
# T-17-B / T-17-C — AdminChargebackListView / AdminChargebackDetailView
# =============================================================================

class AdminChargebackListView(APIView):
    """
    GET /api/v2/admin/chargebacks/
    Lista todos los contracargos registrados. T-17-B.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'payments.view'

    @extend_schema(
        summary='Listado de contracargos (admin)',
        responses={200: ChargebackSerializer(many=True)},
        tags=['payments-admin'],
    )
    def get(self, request):
        qs = Chargeback.objects.select_related('payment').order_by('-created_at')
        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)
        return Response(ChargebackSerializer(qs, many=True).data)


class AdminChargebackDetailView(APIView):
    """
    GET /api/v2/admin/chargebacks/<chargeback_id>/
    Detalle de un contracargo individual. T-17-C.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'payments.view'

    @extend_schema(
        summary='Detalle de contracargo (admin)',
        responses={
            200: ChargebackSerializer,
            404: OpenApiResponse(description='Contracargo no encontrado.'),
        },
        tags=['payments-admin'],
    )
    def get(self, request, chargeback_id):
        chargeback = get_object_or_404(Chargeback, pk=chargeback_id)
        return Response(ChargebackSerializer(chargeback).data)


# =============================================================================
# API v2 — Checkout API (ADR-018, pago en sitio sin redirección)
# =============================================================================

class CheckoutApiPaymentView(APIView):
    """
    POST /api/v2/payments/initiate/
    Procesa un pago con MercadoPago Checkout API (pago en sitio).
    ADR-018: Checkout API sobre Checkout Pro para UX transparente.
    BR-009: las credenciales del gateway NUNCA aparecen en la respuesta.
    DEC-BC-22: select_for_update() previene doble pago concurrente.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'initiate_payment'

    @extend_schema(
        request=CheckoutApiPaymentSerializer,
        responses={
            201: CheckoutApiResponseSerializer,
            200: CheckoutApiResponseSerializer,
            400: OpenApiResponse(description='Serializer inválido'),
            404: OpenApiResponse(description='Orden no encontrada o no es del usuario'),
            422: OpenApiResponse(description='AMOUNT_MISMATCH o estado de orden inválido'),
            502: OpenApiResponse(description='Error del gateway MercadoPago'),
        },
        summary='Crear pago con Checkout API',
    )
    def post(self, request):
        serializer = CheckoutApiPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data

        with db_transaction.atomic():
            try:
                order = (
                    Order.objects
                    .select_for_update()
                    .get(
                        order_number=data['order_number'],
                        user=request.user,
                        status=Order.STATUS_PENDING,
                    )
                )
            except Order.DoesNotExist:
                return Response(
                    {'codigo_error': 'ORDER_NOT_FOUND'},
                    status=404,
                )

            if 'expected_amount' in data and data['expected_amount'] is not None:
                order_total = order.value.total
                if abs(data['expected_amount'] - order_total) > Decimal('0.01'):
                    return Response(
                        {
                            'codigo_error': 'AMOUNT_MISMATCH',
                            'expected':     str(data['expected_amount']),
                            'actual':       str(order_total),
                        },
                        status=422,
                    )

            try:
                payment, result = initiate_checkout_api_payment(
                    order=order,
                    token=data.get('token', ''),
                    installments=data.get('installments', 1),
                    payment_method_id=data.get('payment_method_id', ''),
                    issuer_id=data.get('issuer_id', ''),
                    payer_email=data.get('payer_email', ''),
                    payer_identification_type=data.get('payer_identification_type', ''),
                    payer_identification_number=data.get('payer_identification_number', ''),
                )
            except ValueError as exc:
                return Response(
                    {'codigo_error': 'PAYMENT_ERROR', 'detail': str(exc)},
                    status=422,
                )
            except RuntimeError as exc:
                return Response(
                    {'codigo_error': 'GATEWAY_ERROR', 'detail': str(exc)},
                    status=502,
                )

        response_data = {
            'payment_id':            payment.pk,
            'gateway_payment_id':    result.gateway_payment_id,
            'status':                result.status,
            'status_detail':         result.status_detail,
            'order_number':          order.order_number,
            'amount':                str(result.amount),
            'installments':          result.installments,
            'external_resource_url': result.external_resource_url or '',
            'date_of_expiration':    result.date_of_expiration or '',
            'transaction_data':      result.transaction_data,
        }
        http_status = 201 if result.status == 'approved' else 200
        return Response(response_data, status=http_status)


class MpPublicKeyView(APIView):
    """
    GET /api/v2/payments/public-key/
    Retorna la public_key de MercadoPago para inicializar MP.js en el frontend.
    BR-009: la public_key SÍ puede ir al frontend; el access_token NUNCA.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: MpPublicKeySerializer,
            503: OpenApiResponse(description='Gateway no configurado'),
        },
        summary='Obtener public key de MercadoPago',
    )
    def get(self, request):
        try:
            public_key = get_mp_public_key()
        except ValueError as exc:
            return Response(
                {'codigo_error': 'GATEWAY_NOT_CONFIGURED', 'detail': str(exc)},
                status=503,
            )
        return Response({'public_key': public_key})


class MpCustomerView(APIView):
    """
    GET /api/v2/payments/customer/
    Retorna si el usuario autenticado tiene un customer_id de MercadoPago.
    BR-009: access_token NUNCA en la respuesta.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        customer_id = request.user.mp_customer_id or ''
        return Response({
            'has_customer':   bool(customer_id),
            'mp_customer_id': customer_id,
        })


class MpCustomerCardsView(APIView):
    """
    GET  /api/v2/payments/cards/  — lista tarjetas activas del usuario.
    POST /api/v2/payments/cards/  — guarda nueva tarjeta con verificación por email.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cards = SavedCard.objects.filter(
            user=request.user,
            status=SavedCard.STATUS_ACTIVE,
        )
        data = [
            {
                'id':               c.mp_card_id,
                'last_four_digits': c.last_four_digits,
                'first_six_digits': c.first_six_digits,
                'expiration_month': c.expiration_month,
                'expiration_year':  c.expiration_year,
                'payment_method_id': c.payment_method_id,
                'cardholder_name':  c.cardholder_name,
                'status':           c.status,
            }
            for c in cards
        ]
        return Response(data)

    def post(self, request):
        serializer = MpSaveCardSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        token = serializer.validated_data['token']

        customer_id = get_or_create_mp_customer(request.user)
        if not customer_id:
            return Response(
                {'codigo_error': 'MP_CUSTOMER_ERROR',
                 'detail': 'No se pudo obtener o crear el customer de MercadoPago.'},
                status=502,
            )

        try:
            gateway = MercadoPagoGateway()
            card_data = gateway.save_card(customer_id, token)
        except RuntimeError as exc:
            return Response(
                {'codigo_error': 'GATEWAY_ERROR', 'detail': str(exc)},
                status=502,
            )

        saved_card, created = SavedCard.objects.get_or_create(
            user=request.user,
            mp_card_id=str(card_data['id']),
            defaults={
                'mp_customer_id':   customer_id,
                'last_four_digits': card_data.get('last_four_digits', ''),
                'first_six_digits': card_data.get('first_six_digits', ''),
                'expiration_month': card_data.get('expiration_month', 0),
                'expiration_year':  card_data.get('expiration_year', 0),
                'payment_method_id': (
                    card_data.get('payment_method', {}).get('id', '')
                    if card_data.get('payment_method') else ''
                ),
                'cardholder_name':  (
                    card_data.get('cardholder', {}).get('name', '')
                    if card_data.get('cardholder') else ''
                ),
            },
        )

        if created:
            user = request.user
            user_name = getattr(user, 'first_name', '') or user.email
            send_card_verification_email(
                user_email=user.email,
                user_name=user_name,
                verification_token=saved_card.verification_token,
                last_four=saved_card.last_four_digits,
            )

        return Response(
            {
                'id':               saved_card.mp_card_id,
                'last_four_digits': saved_card.last_four_digits,
                'status':           saved_card.status,
                'verification_sent': created,
            },
            status=201 if created else 200,
        )


class MpCustomerCardDetailView(APIView):
    """
    GET    /api/v2/payments/cards/{card_id}/  — detalle de tarjeta activa.
    PUT    /api/v2/payments/cards/{card_id}/  — actualiza vencimiento/titular.
    DELETE /api/v2/payments/cards/{card_id}/  — elimina la tarjeta.
    """
    permission_classes = [IsAuthenticated]

    def _get_saved_card(self, request, card_id):
        try:
            return SavedCard.objects.get(
                user=request.user,
                mp_card_id=card_id,
                status__in=[SavedCard.STATUS_ACTIVE, SavedCard.STATUS_PENDING],
            )
        except SavedCard.DoesNotExist:
            return None

    def get(self, request, card_id):
        saved = self._get_saved_card(request, card_id)
        if not saved:
            return Response({'codigo_error': 'CARD_NOT_FOUND'}, status=404)
        return Response({
            'id':               saved.mp_card_id,
            'last_four_digits': saved.last_four_digits,
            'first_six_digits': saved.first_six_digits,
            'expiration_month': saved.expiration_month,
            'expiration_year':  saved.expiration_year,
            'payment_method_id': saved.payment_method_id,
            'cardholder_name':  saved.cardholder_name,
            'status':           saved.status,
        })

    def put(self, request, card_id):
        saved = self._get_saved_card(request, card_id)
        if not saved:
            return Response({'codigo_error': 'CARD_NOT_FOUND'}, status=404)

        serializer = MpUpdateCardSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        mp_payload = {}
        if 'expiration_month' in serializer.validated_data:
            mp_payload['expiration_month'] = serializer.validated_data['expiration_month']
        if 'expiration_year' in serializer.validated_data:
            mp_payload['expiration_year'] = serializer.validated_data['expiration_year']
        if 'cardholder_name' in serializer.validated_data:
            mp_payload['cardholder'] = {'name': serializer.validated_data['cardholder_name']}

        try:
            gateway = MercadoPagoGateway()
            gateway.update_customer_card(saved.mp_customer_id, card_id, mp_payload)
        except RuntimeError as exc:
            return Response(
                {'codigo_error': 'GATEWAY_ERROR', 'detail': str(exc)},
                status=502,
            )

        update_fields = []
        if 'expiration_month' in serializer.validated_data:
            saved.expiration_month = serializer.validated_data['expiration_month']
            update_fields.append('expiration_month')
        if 'expiration_year' in serializer.validated_data:
            saved.expiration_year = serializer.validated_data['expiration_year']
            update_fields.append('expiration_year')
        if 'cardholder_name' in serializer.validated_data:
            saved.cardholder_name = serializer.validated_data['cardholder_name']
            update_fields.append('cardholder_name')
        if update_fields:
            update_fields.append('updated_at')
            saved.save(update_fields=update_fields)

        return Response({
            'id':               saved.mp_card_id,
            'last_four_digits': saved.last_four_digits,
            'expiration_month': saved.expiration_month,
            'expiration_year':  saved.expiration_year,
            'cardholder_name':  saved.cardholder_name,
            'status':           saved.status,
        })

    def delete(self, request, card_id):
        saved = self._get_saved_card(request, card_id)
        if not saved:
            return Response({'codigo_error': 'CARD_NOT_FOUND'}, status=404)

        try:
            gateway = MercadoPagoGateway()
            gateway.delete_customer_card(saved.mp_customer_id, card_id)
        except RuntimeError as exc:
            return Response(
                {'codigo_error': 'GATEWAY_ERROR', 'detail': str(exc)},
                status=502,
            )

        saved.status = SavedCard.STATUS_DELETED
        saved.save(update_fields=['status', 'updated_at'])
        return Response(status=204)


class MpPaymentMethodsView(APIView):
    """
    GET /api/v2/payments/methods/
    Retorna la lista de métodos de pago disponibles de MercadoPago.
    BR-009: solo devuelve datos públicos (id, nombre, tipo, thumbnail).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            gateway = MercadoPagoGateway()
            methods = gateway.get_payment_methods()
        except ValueError as exc:
            return Response(
                {'codigo_error': 'GATEWAY_NOT_CONFIGURED', 'detail': str(exc)},
                status=503,
            )
        return Response(methods)


class MpCardVerifyView(APIView):
    """
    GET /api/v2/payments/cards/verify/{token}/
    Activa una tarjeta guardada cuando el usuario hace clic en el enlace
    del email de verificación. Idempotente.
    """
    permission_classes = []

    def get(self, request, token):
        try:
            card = SavedCard.objects.get(verification_token=token)
        except SavedCard.DoesNotExist:
            return Response(
                {'codigo_error': 'TOKEN_INVALID', 'detail': 'Enlace inválido o ya usado.'},
                status=404,
            )

        if card.status == SavedCard.STATUS_DELETED:
            return Response(
                {'codigo_error': 'CARD_DELETED', 'detail': 'La tarjeta fue eliminada.'},
                status=410,
            )

        if card.status != SavedCard.STATUS_ACTIVE:
            card.status = SavedCard.STATUS_ACTIVE
            card.save(update_fields=['status', 'updated_at'])

        return Response({
            'message':          '¡Tu tarjeta ha sido activada exitosamente!',
            'last_four_digits': card.last_four_digits,
            'status':           card.status,
        })


class ZeroDollarAuthView(APIView):
    """
    POST /api/v2/payments/cards/validate/
    Valida una tarjeta sin cargo real usando Zero Dollar Auth (T-15).
    BR-009: access_token nunca sale del backend.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ZeroDollarAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        try:
            result = MercadoPagoGateway().zero_dollar_auth(
                token=data['token'],
                payment_method_id=data['payment_method_id'],
                payer_email=request.user.email,
            )
        except RuntimeError as exc:
            return Response(
                {'codigo_error': 'GATEWAY_ERROR', 'detail': str(exc)},
                status=502,
            )

        return Response({'valid': result.get('status') == 'approved'})
