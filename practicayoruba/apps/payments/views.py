"""
Views — apps.payments
Sprint 15 — UC-PAY-01, UC-PAY-01-EXT, UC-ORD-01-EXT
"""
import logging
from decimal import Decimal

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    extend_schema, OpenApiResponse, OpenApiParameter,
)
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.proxy_models import DeliveredOrder

from .models import Payment
from .serializers import (
    InitiatePaymentSerializer, InitiatePaymentResponseSerializer,
    InstallmentPlansResponseSerializer, PaymentSerializer,
    PaymentReturnSerializer, CheckoutEligibilitySerializer,
    ExpressCheckoutSerializer, RefundRequestSerializer,
    RefundSerializer, RetryEligibilitySerializer,
)
from .services import initiate_payment, handle_gateway_return, get_installment_plans
from apps.users.models import Address
from apps.settings_app.models import ShippingMethod
from apps.cart.models import Cart
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from django.db import transaction as db_transaction
from apps.inventory.services import InventoryService, InsufficientStockError
from apps.settings_app.models import SiteSettings, ShippingMethod
from decimal import Decimal as Dec
from .services import get_payment_status
from .serializers import PaymentStatusSerializer as PSS
from .services import get_payment_history
from .models import Payment as PaymentModel
from .services import execute_refund
from .serializers import RefundRequestSerializer as RRS, RefundSerializer
from .services import get_retry_eligibility
from .serializers import RetryEligibilitySerializer
from .serializers import RefundRequestSerializer, RefundSerializer

logger = logging.getLogger('apps')


# =============================================================================
# UC-PAY-01 — Procesar Pago con MercadoPago
# =============================================================================

class InitiatePaymentView(APIView):
    """
    POST /api/v1/payments/initiate/
    Crea la preferencia de pago en el gateway y retorna la URL de checkout.
    UC-PAY-01 (FR-PAY-01.01, FR-PAY-01.02).

    El comprador debe ser redirigido a checkout_url.
    Las credenciales del gateway NUNCA aparecen en la respuesta (BR-009).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Iniciar pago con MercadoPago',
        description=(
            'Crea una preferencia de pago en MercadoPago y retorna la URL '
            'de checkout. El frontend redirige al comprador a esa URL. '
            'Las credenciales del gateway no aparecen en la respuesta (BR-009).'
        ),
        request=InitiatePaymentSerializer,
        responses={
            201: InitiatePaymentResponseSerializer,
            400: OpenApiResponse(description='Orden no encontrada o no en estado PENDING.'),
            503: OpenApiResponse(description='Gateway de pago no disponible.'),
        },
        tags=['payments'],
    )
    def post(self, request):
        s = InitiatePaymentSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        order_number = s.validated_data['order_number']
        installments  = s.validated_data['installments']
        gateway_type  = s.validated_data.get('gateway', 'MERCADOPAGO')

        # Buscar la orden — solo el dueño puede pagarla
        try:
            if request.user.is_authenticated:
                order = Order.objects.select_related('value').get(
                    order_number=order_number,
                    user=request.user,
                )
            else:
                order = Order.objects.select_related('value').get(
                    order_number=order_number
                )
        except Order.DoesNotExist:
            raise ValidationError({
                'order_number': f'Orden {order_number!r} no encontrada.',
                'codigo_error': 'ORDEN_NO_ENCONTRADA',
            })

        if order.status != Order.STATUS_PENDING:
            raise ValidationError({
                'detail': f'La orden no está en estado PENDING (estado: {order.status}).',
                'codigo_error': 'ORDEN_NO_PAGABLE',
            })

        try:
            payment, checkout_url = initiate_payment(
                order=order,
                request=request,
                installments=installments,
                gateway_type=gateway_type,
            )
        except ValueError as exc:
            raise ValidationError({'detail': str(exc), 'codigo_error': 'GATEWAY_CONFIG_ERROR'})
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'GATEWAY_NO_DISPONIBLE'},
                status=503,
            )

        return Response(
            InitiatePaymentResponseSerializer({
                'payment_id':   payment.pk,
                'checkout_url': checkout_url,
                'order_number': order.order_number,
                'amount':       payment.amount,
                'installments': payment.installments,
            }).data,
            status=201,
        )


class PaymentReturnView(APIView):
    """
    GET /api/v1/payments/<order_number>/return/
    Recibe el retorno del comprador desde el gateway.
    UC-PAY-01 paso 10.

    El estado definitivo llega via webhook (UC-PAY-03, Sprint 16).
    Este endpoint actualiza el Payment si MP confirma 'approved' en los query params.
    Siempre retorna HTTP 200 — el frontend debe verificar el status del pago.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Retorno del gateway de pago',
        description=(
            'MP redirige al comprador aquí tras el pago. '
            'El estado definitivo llega via webhook (Sprint 16). '
            'Retorna siempre 200 — el frontend verifica payment.status.'
        ),
        parameters=[
            OpenApiParameter('order_number', str, location='path'),
            OpenApiParameter('status', str, description='Estado indicado por MP'),
            OpenApiParameter('payment_id', str, description='ID del pago en MP'),
        ],
        responses={200: PaymentSerializer},
        tags=['payments'],
    )
    def get(self, request, order_number):
        s = PaymentReturnSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)

        payment = handle_gateway_return(
            order_number=order_number,
            mp_payment_id=s.validated_data.get('payment_id') or request.query_params.get('payment_id'),
            status=s.validated_data.get('status', 'pending'),
        )
        if not payment:
            return Response({'detail': 'Pago no encontrado.', 'status': 'not_found'}, status=200)

        return Response(PaymentSerializer(payment).data, status=200)


# =============================================================================
# UC-PAY-01-EXT — Cuotas MSI
# =============================================================================

class InstallmentPlansView(APIView):
    """
    GET /api/v1/payments/installments/?order_number=xxx
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
            raise ValidationError({'order_number': 'Requerido.', 'codigo_error': 'ORDER_NUMBER_REQUERIDO'})

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
    GET /api/v1/checkout/eligibility/
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
    POST /api/v1/checkout/express/
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
                'codigo_error': 'NO_ELEGIBLE_EXPRESS',
            })

        # Obtener carrito del usuario
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            raise ValidationError({'detail': 'No tienes un carrito activo.', 'codigo_error': 'CARRITO_VACIO'})

        if not cart.items.exists():
            raise ValidationError({'detail': 'El carrito está vacío.', 'codigo_error': 'CARRITO_VACIO'})

        # Reutilizar el servicio de checkout de UC-ORD-01
        from apps.orders.views import CheckoutView
        from apps.orders.serializers import CheckoutSerializer

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
        inner_request = factory.post('/api/v1/checkout/', checkout_data, format='json')
        inner_request.user = request.user
        inner_request.auth = request.auth
        inner_request._request = request._request

        checkout_view = CheckoutView.as_view()
        drf_request = Request(inner_request)
        drf_request.user = request.user

        # Ejecutar el checkout directamente
        from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress

        cart_items = list(cart.items.select_related('product', 'variant__product', 'variant__option').all())
        check_items = [{'product': ci.product, 'variant': ci.variant, 'quantity': ci.quantity} for ci in cart_items]

        insufficient = InventoryService.check_availability(check_items)
        if insufficient:
            return Response({'detail': 'Stock insuficiente.', 'codigo_error': 'STOCK_INSUFICIENTE', 'items': insufficient}, status=409)

        settings_obj = SiteSettings.get_current()
        iva_rate = settings_obj.iva_rate
        shipping = ShippingMethod.objects.get(pk=shipping_id)
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
                    label    = ci.variant.option.label if ci.variant else ''
                    sku      = ci.variant.sku if ci.variant else ci.product.sku
                    item_sub = ci.unit_price * ci.quantity
                    subtotal += item_sub
                    OrderItem.objects.create(
                        order=order, variant=ci.variant,
                        product_name=ci.product.name,
                        variant_label=label, sku=sku,
                        unit_price=ci.unit_price, quantity=ci.quantity, subtotal=item_sub,
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

                cart.items.all().delete()
                cart.voucher = None
                cart.save(update_fields=['voucher'])

        except InsufficientStockError as exc:
            return Response({'detail': str(exc), 'codigo_error': 'STOCK_INSUFICIENTE'}, status=409)

        from apps.orders.serializers import OrderSerializer
        return Response(OrderSerializer(order).data, status=201)


# =============================================================================
# Sprint 17 — UC-PAY-05, UC-PAY-06, UC-PAY-07, UC-PAY-08, UC-PAY-09
# =============================================================================

class PaymentStatusView(APIView):
    """
    GET /api/v1/payments/<order_number>/status/
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
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDEN_NO_ENCONTRADA'},
                status=404,
            )
        return Response(PSS(result).data)


class PaymentHistoryView(APIView):
    """
    GET /api/v1/payments/<order_number>/history/
    Retorna todos los pagos de una orden ordenados por -created_at.
    UC-PAY-06. RNF-SEC-003.
    """
    permission_classes = [IsAuthenticated]

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
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDEN_NO_ENCONTRADA'},
                status=404,
            )
        return Response(history)


class RefundView(APIView):
    """
    POST /api/v1/payments/<order_number>/refund/
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
        from apps.orders.models import Order

        # RNF-SEC-003: usar filter+first, nunca get con user separado
        order = Order.objects.filter(
            order_number=order_number, user=request.user
        ).first()
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDEN_NO_ENCONTRADA'},
                status=404,
            )

        payment = (
            PaymentModel.objects.filter(order=order, status=PaymentModel.STATUS_APPROVED)
            .order_by('-created_at').first()
        )
        if not payment:
            return Response(
                {'detail': 'No hay pago aprobado en esta orden.',
                 'codigo_error': 'PAGO_NO_REEMBOLSABLE'},
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
            return Response({'detail': str(exc), 'codigo_error': 'PAGO_NO_REEMBOLSABLE'},
                            status=400)
        except RuntimeError as exc:
            return Response({'detail': str(exc), 'codigo_error': 'GATEWAY_NO_DISPONIBLE'},
                            status=503)

        return Response(RefundSerializer(refund).data, status=201)


class RetryEligibilityView(APIView):
    """
    GET /api/v1/payments/<order_number>/retry-eligibility/
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
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDEN_NO_ENCONTRADA'},
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
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Reembolso manual (admin)',
        description=(
            'El admin puede reembolsar cualquier Payment aprobado '
            'independientemente del estado de la orden. '
            'Reutiliza execute_refund() del servicio — mismo código que UC-PAY-07.'
        ),
        request=RefundRequestSerializer,
        responses={
            201: RefundSerializer,
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
            return Response({'detail': str(exc), 'codigo_error': 'PAGO_NO_REEMBOLSABLE'},
                            status=400)
        except RuntimeError as exc:
            return Response({'detail': str(exc), 'codigo_error': 'GATEWAY_NO_DISPONIBLE'},
                            status=503)

        return Response(RefundSerializer(refund).data, status=201)
