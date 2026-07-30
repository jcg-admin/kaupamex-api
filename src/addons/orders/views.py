"""
Views — addons.orders
UC-ORD-01: Checkout, UC-ORD-02..06: Gestión del comprador (Sprint 18)
"""
import json as _json
from decimal import Decimal
from django.db import IntegrityError
from .signals import order_created as order_created_signal
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from addons.users.audit import audit_log_business
from addons.users.models import BusinessEvent
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from addons.authz.permissions import HasCapability
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from addons.inventory.services import InsufficientStockError
from addons.delivery.models.sale_order import set_delivery_line
from addons.sale_loyalty.models.sale_order import set_reward_line
from .models import CheckoutAttempt, Order, OrderItem
from addons.sale.status_projection import filter_orders_by_status, CANONICAL_ORDER_STATUSES
from addons.sale.models import SaleOrder
from .serializers import CancelOrderSerializer, CheckoutSerializer, OrderListSerializer, OrderSerializer, UpdateAddressSerializer, UpdateShippingSerializer
from addons.delivery.quoting import resolve_shipping_quote
from django.db.models import Prefetch
from addons.catalogue.models import ProductImage
from .services import (
    DraftOrderError, OrderNotEditableError, ShippingMethodNotAvailableError,
    cancel_order, confirm_draft_order, get_draft_totals,
    update_order_address, update_shipping_method,
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
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'checkout'

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
        # DEC-BC-03: Idempotency-Key — retorna respuesta cacheada si existe.
        idempotency_key = request.headers.get('Idempotency-Key')
        if idempotency_key and request.user and request.user.is_authenticated:
            try:
                attempt = CheckoutAttempt.objects.get(
                    user=request.user,
                    idempotency_key=idempotency_key,
                )
                return Response(_json.loads(attempt.response_json), status=201)
            except CheckoutAttempt.DoesNotExist:
                pass  # silent OK because no hay intento previo: el checkout sigue su flujo normal

        s = CheckoutSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data

        # 1. Recuperar el draft — V2 unificación orders→sale: el carrito
        # ES la SaleOrder(draft) canónica (sale.order state='draft').
        if request.user and request.user.is_authenticated:
            order = (
                SaleOrder.objects
                .filter(partner=request.user, state=SaleOrder.STATE_DRAFT)
                .order_by('-created_at')
                .first()
            )
            if order is None:
                raise ValidationError({'detail': 'No tienes un carrito activo.',
                                       'codigo_error': 'EMPTY_CART'})
            guest_email = None
        else:
            cart_token = data.get('cart_token')
            if not cart_token:
                raise ValidationError({'cart_token': 'Requerido para visitantes anónimos.',
                                       'codigo_error': 'CART_TOKEN_REQUIRED'})
            guest_email = data.get('guest_email')
            if not guest_email:
                raise ValidationError({'guest_email': 'Requerido para visitantes anónimos.',
                                       'codigo_error': 'GUEST_EMAIL_REQUIRED'})
            order = get_object_or_404(SaleOrder, cart_token=cart_token,
                                      partner__isnull=True,
                                      state=SaleOrder.STATE_DRAFT)

        # 2. Cotización de envío (sin cambio de política: envío GRATIS —
        # REVIERTE DEC-BC-25; el comprador no elige método, el costo se
        # deriva por zona vía resolve_shipping_quote, hoy Decimal('0.00')).
        # DEC-BC-18: la cobertura de zona la valida CheckoutSerializer.
        zip_code = (data.get('address') or {}).get('zip_code', '')
        totals = get_draft_totals(order)
        subtotal_for_shipping = Decimal(totals['subtotal_net'])
        quote = resolve_shipping_quote(zip_code, subtotal_for_shipping)
        shipping_cost = quote.cost

        # 3. Transición DRAFT→PENDING (adaptación de sale.order.action_confirm):
        # nada se copia ni se borra — el servicio congela snapshot (precio
        # vigente H-CICLO78-04), crea OrderValue/OrderAddress, consume el
        # voucher (DEC-VCU-01/DEC-BC-10) y libera el cart_token.
        # E1-bis: los importes que NO son de producto se materializan como
        # LÍNEAS del draft ANTES de confirmar — mismo orden que Odoo (el
        # wizard agrega la línea a la cotización; luego se confirma). Cada
        # addon contribuye la suya: `delivery` el envío, `sale_loyalty` el
        # descuento. `sale` no las conoce (dirección de dependencia).
        set_delivery_line(order, shipping_cost)
        set_reward_line(order)

        user = request.user if request.user.is_authenticated else None
        try:
            order = confirm_draft_order(
                order,
                address_data=data['address'],
                guest_email=guest_email,
                notes=data.get('notes', ''),
                shipping_cost=shipping_cost,
            )
        except DraftOrderError as exc:
            if exc.codigo_error == 'INSUFFICIENT_STOCK':
                return Response({'detail': 'Stock insuficiente para algunos items.',
                                 'codigo_error': 'INSUFFICIENT_STOCK',
                                 'items': getattr(exc, 'items', [])}, status=409)
            if exc.codigo_error == 'VOUCHER_EXHAUSTED':
                return Response({'detail': str(exc),
                                 'codigo_error': 'VOUCHER_EXHAUSTED'}, status=409)
            raise ValidationError({'detail': str(exc),
                                   'codigo_error': exc.codigo_error})
        except InsufficientStockError as exc:
            return Response({'detail': str(exc),
                             'codigo_error': 'INSUFFICIENT_STOCK',
                             'stock_disponible': exc.available}, status=409)
        except IntegrityError:
            return Response({
                'detail': 'Este voucher ya fue utilizado en tu cuenta.',
                'codigo_error': 'VOUCHER_ALREADY_USED',
            }, status=409)

        audit_log_business(
            user if user and user.is_authenticated else None,
            BusinessEvent.ACTION_ORDER_CREATED,
            request,
            target_type=BusinessEvent.TARGET_ORDER,
            target_id=order.pk,
            extra={'order_number': order.order_number},
        )

        # DEC-BC-19: señal order_created para notificaciones/hooks downstream.
        order_created_signal.send(sender=Order, order=order)

        # Re-fetch con select_related/prefetch para evitar N+1 al serializar:
        # OrderSerializer accede a items, value, address y shipping_method.
        order = (
            Order.objects
            .select_related('value', 'address', 'shipping_method', 'sale_order')
            .prefetch_related('items')
            .get(pk=order.pk)
        )
        response_data = OrderSerializer(order).data

        # DEC-BC-03: guardar respuesta para idempotencia futura.
        if idempotency_key and user:
            CheckoutAttempt.objects.create(
                user=user,
                idempotency_key=idempotency_key,
                response_json=_json.dumps(response_data),
            )

        return Response(response_data, status=201)


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
            .select_related('value', 'shipping_method', 'sale_order')
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
        # filtro por ?status=<STATUS>. O2C rebanada 6: el contrato público se
        # re-especifica contra el vocabulario canónico (6 valores) y se traduce
        # a los ejes canónicos, sin depender de la columna espejo (retirada en
        # V5d). Los 3 valores muertos del enum legacy quedan fuera → 400.
        status_filter = request.query_params.get('status')
        if status_filter:
            try:
                qs = filter_orders_by_status(qs, status_filter)
            except ValueError:
                return Response(
                    {'detail': (f'Status invalido: {status_filter}. Validos: '
                                f'{list(CANONICAL_ORDER_STATUSES)}.'),
                     'codigo_error': 'INVALID_STATUS'},
                    status=400,
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
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.orders'

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
            .select_related('value', 'address', 'shipping_method', 'sale_order')
            # H-CICLO104-07: prefetch status_logs so OrderSerializer can
            # include them without N+1; OrderDetailPage.jsx uses them for
            # the timeline step dates.
            .prefetch_related('items', 'status_logs__changed_by')
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
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.orders'

    @extend_schema(
        summary='[DEPRECATED → /api/v2/orders/<n>/cancellations/] Cancelar una orden',
        deprecated=True,
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
            .select_related('value', 'shipping_method', 'sale_order')
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
        # Re-fetch con select_related/prefetch para evitar N+1 al serializar.
        # OrderSerializer accede a items, value, address, shipping_method.
        order = (
            Order.objects
            .select_related('value', 'address', 'shipping_method', 'sale_order')
            .prefetch_related('items')
            .get(pk=order.pk)
        )
        return Response(OrderSerializer(order).data)


class OrderAddressUpdateView(APIView):
    """
    PATCH /api/v1/orders/<order_number>/address/
    Edita la dirección de entrega de una orden.
    UC-ORD-05 (FR-ORD-05.02).
    Solo posible en PENDING, PROCESSING, IN_PREPARATION.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.orders'

    @extend_schema(
        summary='[DEPRECATED → /api/v2/orders/<n>/shipping-address/] Actualizar dirección de entrega',
        deprecated=True,
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
            update_order_address(order, s.validated_data, changed_by=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc), 'codigo_error': 'ADDRESS_NOT_EDITABLE'},
                status=400,
            )

        # Re-fetch con select_related/prefetch para evitar N+1 al serializar.
        order = (
            Order.objects
            .select_related('value', 'address', 'shipping_method', 'sale_order')
            .prefetch_related('items')
            .get(pk=order.pk)
        )
        return Response(OrderSerializer(order).data)


class OrderShippingUpdateView(APIView):
    """
    PATCH /api/v1/orders/<order_number>/shipping/
    Cambia el método de envío y recalcula el total.
    UC-ORD-06 (FR-ORD-06.02).
    Solo posible en PENDING, PROCESSING, IN_PREPARATION.
    H-ORD-007: recalcula total = neto + tax + nuevo_shipping_cost.

    DEPRECADO (2026-07-07): el comprador NUNCA elige método de envío — el
    envío se deriva por zona y es GRATIS (open-closed; supersede
    DEC-BC-19/DEC-BC-25, ver UC-ORD-01 v2.2.0 y UC-ORD-06 marcado deprecado).
    "Cambiar el método de envío" como acción del comprador ya no aplica. El
    endpoint se conserva (no se elimina) marcado deprecado; su retiro efectivo
    queda para una iniciativa dedicada.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.orders'

    @extend_schema(
        summary='[DEPRECATED → /api/v2/orders/<n>/shipping-method/] Cambiar método de envío',
        deprecated=True,
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
            .select_related('value', 'shipping_method', 'sale_order')
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
            update_shipping_method(
                order, s.validated_data['shipping_method_id'],
                changed_by=request.user,
            )
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

        # Re-fetch con select_related/prefetch para evitar N+1 al serializar.
        order = (
            Order.objects
            .select_related('value', 'address', 'shipping_method', 'sale_order')
            .prefetch_related('items')
            .get(pk=order.pk)
        )
        return Response(OrderSerializer(order).data)


class OrderCollectionV2View(APIView):
    """
    GET  /api/v2/orders/ — historial de ordenes del usuario (UC-ORD-03).
    POST /api/v2/orders/ — crear orden desde carrito / checkout (UC-ORD-01).

    Tier B (mapeo §2.2): coleccion REST canonica unificada. En v1 el
    checkout estaba en /api/v1/checkout/ (ruta separada); v2 lo ubica
    en POST /orders/ siguiendo la convencion REST de coleccion.
    GET requiere auth; POST acepta anonimos con throttle checkout.
    """

    # POST (checkout) queda AllowAny — guest checkout se mantiene (DEC-ENF-03).
    # GET (historial propio) es gestión de cuenta → exige account.orders.
    required_capability = 'account.orders'

    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [IsAuthenticated(), HasCapability()]

    def get_throttles(self):
        if self.request.method == 'POST':
            self.throttle_scope = 'checkout'
            return [ScopedRateThrottle()]
        return []

    def get(self, request, *args, **kwargs):
        return OrderListView().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return CheckoutView().post(request)
