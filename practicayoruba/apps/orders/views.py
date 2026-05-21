"""
Views — apps.orders
UC-ORD-01: Checkout, UC-ORD-02..06: Gestión del comprador (Sprint 18)
"""
import uuid
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from apps.users.audit import audit_log_business
from apps.users.models import BusinessEvent
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.cart.models import Cart, CartItem
from apps.cart.views import _get_or_create_cart
from apps.inventory.services import InventoryService, InsufficientStockError
from apps.settings_app.models import SiteSettings, ShippingMethod
from .models import Order, OrderItem, OrderValue, OrderAddress
from .serializers import CancelOrderSerializer, CheckoutSerializer, OrderListSerializer, OrderSerializer, UpdateAddressSerializer, UpdateShippingSerializer
from django.db.models import Prefetch
from apps.catalogue.models import ProductImage
from .services import OrderNotEditableError, ShippingMethodNotAvailableError, cancel_order, update_order_address, update_shipping_method





class CheckoutView(APIView):
    """
    POST /api/v1/checkout/
    Crea una orden desde el carrito activo. UC-ORD-01.
    Soporta usuarios autenticados y visitantes anónimos (BR-011).

    Flujo:
    1. Recuperar carrito (por JWT o cart_token).
    2. Verificar que el carrito tenga items.
    3. Verificar disponibilidad de todos los items.
    4. Iniciar transacción atómica:
       a. Decrementar stock con SELECT FOR UPDATE (FR-ORD-01.02).
       b. Crear Order, OrderItems (snapshot), OrderValue, OrderAddress.
       c. Vaciar el carrito.
    5. Retornar la orden creada.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Crear orden desde carrito (checkout)',
        description=(
            'Convierte el carrito en una orden. '
            'Usuarios autenticados: usar JWT. '
            'Visitantes: enviar cart_token y guest_email. '
            'BR-005: snapshots inmutables de precios y dirección. '
            'BR-011: checkout posible sin autenticación.'
        ),
        request=CheckoutSerializer,
        responses={
            201: OrderSerializer,
            400: OpenApiResponse(description='Datos inválidos o carrito vacío.'),
            409: OpenApiResponse(description='Stock insuficiente para algún item.'),
        },
        tags=['orders'],
    )
    def post(self, request):
        s = CheckoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        # 1. Recuperar carrito
        if request.user and request.user.is_authenticated:
            try:
                cart = Cart.objects.get(user=request.user)
            except Cart.DoesNotExist:
                raise ValidationError({'detail': 'No tienes un carrito activo.',
                                       'codigo_error': 'EMPTY_CART'})
        else:
            cart_token = data.get('cart_token')
            if not cart_token:
                raise ValidationError({'cart_token': 'Requerido para visitantes anónimos.',
                                       'codigo_error': 'CART_TOKEN_REQUIRED'})
            guest_email = data.get('guest_email')
            if not guest_email:
                raise ValidationError({'guest_email': 'Requerido para visitantes anónimos.',
                                       'codigo_error': 'GUEST_EMAIL_REQUIRED'})
            cart = get_object_or_404(Cart, cart_token=cart_token, user__isnull=True)

        # 2. Verificar items
        cart_items = list(cart.items.select_related(
            'product', 'variant__product', 'variant__option'
        ).all())
        if not cart_items:
            raise ValidationError({'detail': 'El carrito está vacío.',
                                   'codigo_error': 'EMPTY_CART'})

        # 3. Verificar disponibilidad (sin bloqueo aún)
        check_items = [
            {'product': ci.product, 'variant': ci.variant, 'quantity': ci.quantity}
            for ci in cart_items
        ]
        insufficient = InventoryService.check_availability(check_items)
        if insufficient:
            return Response({'detail': 'Stock insuficiente para algunos items.',
                             'codigo_error': 'INSUFFICIENT_STOCK',
                             'items': insufficient}, status=409)

        # 4. Transacción atómica: decrement + crear orden
        settings_obj = SiteSettings.get_current()
        iva_rate = settings_obj.iva_rate

        # Método de envío
        shipping_method = None
        shipping_cost   = Decimal('0.00')
        if data.get('shipping_method_id'):
            shipping_method = get_object_or_404(
                ShippingMethod, pk=data['shipping_method_id'], is_active=True)
            # free_threshold
            subtotal_for_shipping = cart.get_subtotal() - cart.get_discount()
            if (shipping_method.free_threshold is None or
                    subtotal_for_shipping < shipping_method.free_threshold):
                shipping_cost = shipping_method.cost

        try:
            with transaction.atomic():
                # a. Decrementar stock (SELECT FOR UPDATE dentro del servicio)
                order_items_for_inv = check_items
                InventoryService.decrement(order_items_for_inv)

                # b. Crear Order
                user = request.user if request.user.is_authenticated else None
                guest_email = data.get('guest_email') if not user else None

                # Capturar voucher snapshot
                voucher_code     = cart.voucher.code if cart.voucher else ''
                voucher_discount = cart.get_discount()

                order = Order.objects.create(
                    user=user,
                    guest_email=guest_email,
                    shipping_method=shipping_method,
                    voucher_code=voucher_code,
                    voucher_discount=voucher_discount,
                    notes=data.get('notes', ''),
                )

                # c. Crear OrderItems (snapshot BR-005)
                subtotal = Decimal('0.00')
                for ci in cart_items:
                    label     = ci.variant.option.label if ci.variant else ''
                    sku       = ci.variant.sku if ci.variant else ci.product.sku
                    item_sub  = ci.unit_price * ci.quantity
                    subtotal += item_sub
                    OrderItem.objects.create(
                        order=order,
                        variant=ci.variant,
                        product_name=ci.product.name,
                        variant_label=label,
                        sku=sku,
                        unit_price=ci.unit_price,
                        quantity=ci.quantity,
                        subtotal=item_sub,
                    )

                # d. Crear OrderValue (snapshot financiero)
                net    = subtotal - voucher_discount
                tax    = (net * iva_rate / (1 + iva_rate)).quantize(Decimal('0.01'))
                total  = net + shipping_cost
                OrderValue.objects.create(
                    order=order, subtotal=subtotal, tax=tax,
                    shipping_cost=shipping_cost, discount=voucher_discount, total=total,
                )

                # e. Crear OrderAddress (snapshot de dirección)
                addr_data = data['address']
                OrderAddress.objects.create(order=order, **addr_data)

                # f. Vaciar carrito
                cart.items.all().delete()
                cart.voucher = None
                cart.save(update_fields=['voucher'])

        except InsufficientStockError as exc:
            return Response({'detail': str(exc),
                             'codigo_error': 'INSUFFICIENT_STOCK'}, status=409)

        audit_log_business(
            user if user and user.is_authenticated else None,
            BusinessEvent.ACTION_ORDER_CREATED,
            request,
            target_type=BusinessEvent.TARGET_ORDER,
            target_id=order.pk,
            extra={'order_number': order.order_number},
        )
        return Response(OrderSerializer(order).data, status=201)


# =============================================================================
# Sprint 18 — UC-ORD-02/03/04/05/06 — Gestión del comprador
# =============================================================================

class OrderPagination(PageNumberPagination):
    """10 órdenes por página — RNF-PERF-003."""
    page_size             = 10
    page_size_query_param = 'page_size'
    max_page_size         = 50


class OrderListView(APIView):
    """
    GET /api/v1/orders/
    Lista todas las órdenes del usuario autenticado, paginadas.
    UC-ORD-03 (FR-ORD-03.02). RNF-PERF-003: 10 por página.
    H-ORD-003: thumbnail resuelto desde Product.images, sin N+1.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Historial de órdenes del usuario',
        description=(
            'Lista todas las órdenes del usuario paginadas (10 por página). '
            'Incluye thumbnail del primer ítem, total, y conteo de ítems. '
            'RNF-PERF-003: paginación con page_size ajustable hasta 50.'
        ),
        parameters=[
            OpenApiParameter('page', int, description='Número de página'),
            OpenApiParameter('page_size', int, description='Órdenes por página (max 50)'),
        ],
        responses={200: OrderListSerializer(many=True)},
        tags=['orders'],
        operation_id='orders_list',
    )
    def get(self, request):

        qs = (
            Order.objects.filter(user=request.user)
            .select_related('value', 'shipping_method')
            .prefetch_related(
                Prefetch(
                    'items',
                    queryset=OrderItem.objects.select_related('product')
                             .prefetch_related(
                                 Prefetch(
                                     'product__images',
                                     queryset=ProductImage.objects.filter(is_cover=True)[:1],
                                     to_attr='_images_prefetched',
                                 )
                             ),
                    to_attr='_items_prefetched',
                )
            )
            .order_by('-created_at')
        )

        # UC-ORD-03 PARTE 4.2 Alt-B + PARTE 7.1 (DEC-ORD-07):
        # filtro por ?status=<STATUS>. Antes ignorado.
        status_filter = request.query_params.get('status')
        if status_filter:
            valid_statuses = {choice[0] for choice in Order._meta.get_field('status').choices}
            if status_filter not in valid_statuses:
                return Response(
                    {'detail': f'Status invalido: {status_filter}.',
                     'codigo_error': 'INVALID_STATUS'},
                    status=400,
                )
            qs = qs.filter(status=status_filter)

        paginator = OrderPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = OrderListSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class OrderDetailView(APIView):
    """
    GET /api/v1/orders/<order_number>/
    Devuelve el detalle completo de una orden.
    UC-ORD-02 (FR-ORD-02.02). RNF-SEC-003: filter(order_number, user) → 404.
    Carga anticipada de items, value y address (evita N+1).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Detalle de una orden',
        description=(
            'Retorna el snapshot completo: ítems con precios al momento del '
            'checkout (BR-005), dirección, desglose financiero y estado actual. '
            'RNF-SEC-003: 404 si la orden no existe o no pertenece al usuario.'
        ),
        responses={
            200: OrderSerializer,
            404: OpenApiResponse(description='Orden no encontrada.'),
        },
        tags=['orders'],
        operation_id='orders_retrieve',
    )
    def get(self, request, order_number):

        order = (
            Order.objects
            .filter(order_number=order_number, user=request.user)
            .select_related('value', 'address', 'shipping_method')
            .prefetch_related('items')
            .first()
        )
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )
        return Response(OrderSerializer(order).data)


class OrderCancelView(APIView):
    """
    POST /api/v1/orders/<order_number>/cancel/
    Cancela una orden del comprador.
    UC-ORD-04 (FR-ORD-04.02, FR-ORD-04.03).

    Transacción atómica:
      1. Valida estado cancelable (PENDING, PROCESSING)
      2. Order → CANCELLED + cancellation_reason + cancelled_at
      3. Restaura stock (InventoryService.restore)
      4. Reembolso automático si había Payment aprobado
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Cancelar una orden',
        description=(
            'Cancela una orden en estado PENDING o PROCESSING. '
            'Restaura el stock de todos los ítems. '
            'Si había un pago aprobado, inicia el reembolso automáticamente. '
            'H-ORD-002: solo PENDING y PROCESSING son cancelables por el comprador.'
        ),
        request=CancelOrderSerializer,
        responses={
            200: OrderSerializer,
            400: OpenApiResponse(description='Orden no cancelable.'),
            404: OpenApiResponse(description='Orden no encontrada.'),
            503: OpenApiResponse(description='Gateway de reembolso no disponible.'),
        },
        tags=['orders'],
    )
    def post(self, request, order_number):

        order = (
            Order.objects
            .filter(order_number=order_number, user=request.user)
            .select_related('value', 'shipping_method')
            .prefetch_related('items__product', 'items__variant', 'payments')
            .first()
        )
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )

        s = CancelOrderSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            cancel_order(
                order=order,
                reason=s.validated_data.get('reason', ''),
                cancelled_by=request.user,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'CANCELLATION_NOT_ALLOWED'},
                status=400,
            )
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'GATEWAY_UNAVAILABLE'},
                status=503,
            )

        audit_log_business(
            request.user if request.user.is_authenticated else None,
            BusinessEvent.ACTION_ORDER_CANCELLED,
            request,
            target_type=BusinessEvent.TARGET_ORDER,
            target_id=order.pk,
            extra={'order_number': order.order_number,
                   'reason': s.validated_data.get('reason', '')},
        )
        order.refresh_from_db()
        return Response(OrderSerializer(order).data)


class OrderAddressUpdateView(APIView):
    """
    PATCH /api/v1/orders/<order_number>/address/
    Edita la dirección de entrega de una orden.
    UC-ORD-05 (FR-ORD-05.02).
    Solo posible en PENDING, PROCESSING, IN_PREPARATION.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Actualizar dirección de entrega',
        description=(
            'Actualiza la dirección de entrega de una orden. '
            'Solo posible antes de que se cree la guía de envío '
            '(estados: PENDING, PROCESSING, IN_PREPARATION). '
            'H-ORD-002: los estados editables mapean correctamente al modelo.'
        ),
        request=UpdateAddressSerializer,
        responses={
            200: OrderSerializer,
            400: OpenApiResponse(description='Dirección no editable.'),
            404: OpenApiResponse(description='Orden no encontrada.'),
        },
        tags=['orders'],
    )
    def patch(self, request, order_number):

        order = (
            Order.objects
            .filter(order_number=order_number, user=request.user)
            .select_related('address', 'value')
            .first()
        )
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )

        s = UpdateAddressSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            update_order_address(order, s.validated_data)
        except ValueError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'ADDRESS_NOT_EDITABLE'},
                status=400,
            )

        order.refresh_from_db()
        return Response(OrderSerializer(order).data)


class OrderShippingUpdateView(APIView):
    """
    PATCH /api/v1/orders/<order_number>/shipping/
    Cambia el método de envío y recalcula el total.
    UC-ORD-06 (FR-ORD-06.02).
    Solo posible en PENDING, PROCESSING, IN_PREPARATION.
    H-ORD-007: recalcula total = neto + tax + nuevo_shipping_cost.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Cambiar método de envío',
        description=(
            'Cambia el método de envío de la orden y recalcula el total. '
            'Solo posible antes del envío (PENDING, PROCESSING, IN_PREPARATION). '
            'H-ORD-007: total = subtotal_neto + IVA + costo_nuevo_envío.'
        ),
        request=UpdateShippingSerializer,
        responses={
            200: OrderSerializer,
            400: OpenApiResponse(description='Cambio de envío no permitido.'),
            404: OpenApiResponse(description='Orden no encontrada.'),
        },
        tags=['orders'],
    )
    def patch(self, request, order_number):

        order = (
            Order.objects
            .filter(order_number=order_number, user=request.user)
            .select_related('value', 'shipping_method')
            .first()
        )
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDER_NOT_FOUND'},
                status=404,
            )

        s = UpdateShippingSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            update_shipping_method(order, s.validated_data['shipping_method_id'])
        except OrderNotEditableError as exc:
            # UC-ORD-06 PARTE 7.3 (DEC-ORD-04): 409 ORDER_NOT_EDITABLE.
            return Response(
                {'detail': str(exc), 'codigo_error': 'ORDER_NOT_EDITABLE'},
                status=409,
            )
        except ShippingMethodNotAvailableError as exc:
            # UC-ORD-06 PARTE 7.3 (DEC-ORD-04): 400 SHIPPING_METHOD_NOT_AVAILABLE.
            return Response(
                {'detail': str(exc),
                 'codigo_error': 'SHIPPING_METHOD_NOT_AVAILABLE'},
                status=400,
            )

        order.refresh_from_db()
        return Response(OrderSerializer(order).data)
