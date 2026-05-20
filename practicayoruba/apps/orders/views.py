"""
Views — apps.orders
UC-ORD-01: Checkout, UC-ORD-02..06: Gestión del comprador (Sprint 18)
"""
import uuid
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
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
from .serializers import (
    CancelOrderSerializer, CheckoutSerializer, OrderListSerializer,
    OrderSerializer, UpdateAddressSerializer, UpdateShippingSerializer,
)


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
                                       'codigo_error': 'CARRITO_VACIO'})
        else:
            cart_token = data.get('cart_token')
            if not cart_token:
                raise ValidationError({'cart_token': 'Requerido para visitantes anónimos.',
                                       'codigo_error': 'CART_TOKEN_REQUERIDO'})
            guest_email = data.get('guest_email')
            if not guest_email:
                raise ValidationError({'guest_email': 'Requerido para visitantes anónimos.',
                                       'codigo_error': 'GUEST_EMAIL_REQUERIDO'})
            cart = get_object_or_404(Cart, cart_token=cart_token, user__isnull=True)

        # 2. Verificar items
        cart_items = list(cart.items.select_related(
            'product', 'variant__product', 'variant__option'
        ).all())
        if not cart_items:
            raise ValidationError({'detail': 'El carrito está vacío.',
                                   'codigo_error': 'CARRITO_VACIO'})

        # 3. Verificar disponibilidad (sin bloqueo aún)
        check_items = [
            {'product': ci.product, 'variant': ci.variant, 'quantity': ci.quantity}
            for ci in cart_items
        ]
        insufficient = InventoryService.check_availability(check_items)
        if insufficient:
            return Response({'detail': 'Stock insuficiente para algunos items.',
                             'codigo_error': 'STOCK_INSUFICIENTE',
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
                             'codigo_error': 'STOCK_INSUFICIENTE'}, status=409)

        return Response(OrderSerializer(order).data, status=201)


class OrderDetailView(APIView):
    """GET /api/v1/orders/<order_number>/ — ver detalle de orden."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Ver detalle de orden',
        responses={200: OrderSerializer, 404: None},
        tags=['orders'],
    )
    def get(self, request, order_number):
        qs = Order.objects.select_related(
            'value', 'address', 'shipping_method', 'user'
        ).prefetch_related('items')
        if request.user.is_authenticated:
            order = get_object_or_404(qs, order_number=order_number, user=request.user)
        else:
            return Response(status=403)
        return Response(OrderSerializer(order).data)


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
    )
    def get(self, request):
        from django.db.models import Prefetch
        from .models import Order, OrderItem
        from .serializers import OrderListSerializer
        from apps.catalogue.models import ProductImage

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
    )
    def get(self, request, order_number):
        from .models import Order
        from .serializers import OrderSerializer

        order = (
            Order.objects
            .filter(order_number=order_number, user=request.user)
            .select_related('value', 'address', 'shipping_method')
            .prefetch_related('items')
            .first()
        )
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDEN_NO_ENCONTRADA'},
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
        from .models import Order
        from .serializers import CancelOrderSerializer, OrderSerializer
        from .services import cancel_order

        order = (
            Order.objects
            .filter(order_number=order_number, user=request.user)
            .select_related('value', 'shipping_method')
            .prefetch_related('items__product', 'items__variant', 'payments')
            .first()
        )
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDEN_NO_ENCONTRADA'},
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
                {'detail': str(exc), 'codigo_error': 'CANCELACION_NO_PERMITIDA'},
                status=400,
            )
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'GATEWAY_NO_DISPONIBLE'},
                status=503,
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
        from .models import Order
        from .serializers import UpdateAddressSerializer, OrderSerializer
        from .services import update_order_address

        order = (
            Order.objects
            .filter(order_number=order_number, user=request.user)
            .select_related('address', 'value')
            .first()
        )
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDEN_NO_ENCONTRADA'},
                status=404,
            )

        s = UpdateAddressSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            update_order_address(order, s.validated_data)
        except ValueError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'DIRECCION_NO_EDITABLE'},
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
        from .models import Order
        from .serializers import UpdateShippingSerializer, OrderSerializer
        from .services import update_shipping_method

        order = (
            Order.objects
            .filter(order_number=order_number, user=request.user)
            .select_related('value', 'shipping_method')
            .first()
        )
        if not order:
            return Response(
                {'detail': 'Orden no encontrada.', 'codigo_error': 'ORDEN_NO_ENCONTRADA'},
                status=404,
            )

        s = UpdateShippingSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        try:
            update_shipping_method(order, s.validated_data['shipping_method_id'])
        except ValueError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'METODO_NO_EDITABLE'},
                status=400,
            )

        order.refresh_from_db()
        return Response(OrderSerializer(order).data)
