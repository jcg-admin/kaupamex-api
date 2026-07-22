"""
Views — addons.cart (Sprint 6 · S3 unificación cart→order→sale)

UC-CART-01: Ver carrito activo
UC-CART-02: Agregar ítem al carrito
UC-CART-03: Eliminar ítem del carrito
UC-CART-04: Aplicar voucher al carrito
UC-CART-05: Guardar carrito para después
UC-CART-06: Sincronizar carrito anónimo con cuenta

S3 (analisis-unificar-cart-order-sale): estas vistas conservan el contrato
``/api/v1/cart/*`` (mismos paths, mismos campos ``items``/``totals``, mismos
``codigo_error``) pero sirven y mutan el ``Order(DRAFT)`` — en Odoo el
carrito ES un ``sale.order`` en ``state='draft'``, no una tabla aparte. Los
modelos ``Cart``/``CartItem`` quedan como legado hasta la data migration S4.
"""
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from addons.catalogue.models import Product
from addons.chartsize.models import ProductVariant
from addons.orders.models import Order
from addons.orders.services import (
    DraftOrderError,
    add_item_to_draft,
    apply_voucher_to_draft,
    clear_draft_items,
    get_or_create_draft_order,
    merge_draft_orders,
    remove_draft_item,
    remove_voucher_from_draft,
    update_draft_item_quantity,
)
from config.schema import error_response
from .models import SavedCart, SavedCartItem
from .serializers import (
    AddItemSerializer, DraftCartSerializer, MergeCartSerializer,
    SavedCartSerializer, UpdateItemSerializer,
)


def _get_or_create_draft(request):
    """
    Devuelve (order, created, is_authenticated) — el ``Order(DRAFT)`` que
    hace de carrito activo.
    - Autenticado: draft único del usuario (one-draft-per-user en servicio).
    - Anónimo: draft por token (cookie httpOnly preferida sobre el header
      X-Cart-Token, H-CART-01 Fase 2).
    """
    if request.user.is_authenticated:
        order, created = get_or_create_draft_order(user=request.user)
        return order, created, True
    token = request.COOKIES.get('cart_token') or request.META.get('HTTP_X_CART_TOKEN')
    order, created = get_or_create_draft_order(cart_token=token or None)
    # Señal para CartCookieMiddleware: fija/renueva la cookie con este token.
    # OJO: la vista recibe el Request de DRF (wrapper); el middleware ve el
    # HttpRequest de Django subyacente — marcar el request nativo.
    django_request = getattr(request, '_request', request)
    django_request._anon_cart_token = str(order.cart_token)
    return order, created, False


def _prefetch_draft(order):
    """
    Re-fetch del draft con prefetch para evitar N+1 al serializar
    (H-CICLO46-01 aplicado al draft): DraftItemSerializer toca
    ``item.product.slug``/``images`` y ``item.variant`` (current_price).
    """
    return (
        Order.objects
        .prefetch_related('items__product__images', 'items__variant__option')
        .get(pk=order.pk)
    )


class CartView(APIView):
    """
    GET    /api/v1/cart/  — UC-CART-01 ver carrito activo.
    POST   /api/v1/cart/  — UC-CART-02 agregar ítem.
    DELETE /api/v1/cart/  — vaciar carrito (eliminar todos los ítems).
    """
    permission_classes = [AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'cart'

    @extend_schema(
        summary='Ver carrito activo (UC-CART-01)',
        tags=['cart'],
        responses={200: DraftCartSerializer},
    )
    def get(self, request):
        order, _, _ = _get_or_create_draft(request)
        return Response(DraftCartSerializer(_prefetch_draft(order)).data)

    @extend_schema(
        summary='Agregar ítem al carrito (UC-CART-02)',
        tags=['cart'],
        request=AddItemSerializer,
        responses={200: DraftCartSerializer,
                   400: error_response('Datos inválidos'),
                   409: error_response('Producto sin stock')},
    )
    def post(self, request):
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id')
        try:
            quantity = int(request.data.get('quantity', 1))
        except (ValueError, TypeError):
            raise ValidationError({'quantity': 'Debe ser un entero valido.'})

        if not product_id:
            raise ValidationError({'product_id': 'Requerido.'})
        if quantity < 1:
            raise ValidationError({'quantity': 'Debe ser >= 1.'})

        product = get_object_or_404(Product, pk=product_id, is_active=True, is_published=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)

        order, _, _ = _get_or_create_draft(request)
        try:
            add_item_to_draft(order, product, variant=variant, quantity=quantity)
        except DraftOrderError as exc:
            if exc.codigo_error == 'OUT_OF_STOCK':
                return Response(
                    {'detail': 'Producto sin stock.', 'codigo_error': 'OUT_OF_STOCK'},
                    status=status.HTTP_409_CONFLICT,
                )
            raise ValidationError({'codigo_error': exc.codigo_error,
                                   'quantity': 'Stock insuficiente.'})

        return Response(DraftCartSerializer(_prefetch_draft(order)).data)

    @extend_schema(summary='Vaciar carrito (UC-CART-03)', tags=['cart'],
                   responses={204: None})
    def delete(self, request):
        order, _, _ = _get_or_create_draft(request)
        clear_draft_items(order)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemListView(APIView):
    """
    GET  /api/v1/cart/items/ — UC-CART-01 ver carrito.
    POST /api/v1/cart/items/ — UC-CART-02 agregar ítem (201 create / 200 merge).
    """
    permission_classes = [AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'cart'

    @extend_schema(summary='Listar items del carrito', tags=['cart'],
                   responses={200: DraftCartSerializer})
    def get(self, request):
        order, _, _ = _get_or_create_draft(request)
        return Response(DraftCartSerializer(_prefetch_draft(order)).data)

    @extend_schema(summary='Agregar ítem al carrito (UC-CART-02)', tags=['cart'],
                   request=AddItemSerializer,
                   responses={201: DraftCartSerializer, 200: DraftCartSerializer,
                              400: error_response('Datos inválidos'),
                              404: error_response('Variante no disponible'),
                              409: error_response('Sin stock suficiente')})
    def post(self, request):
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id')
        try:
            quantity = int(request.data.get('quantity', 1))
        except (ValueError, TypeError):
            raise ValidationError({'quantity': 'Debe ser un entero valido.'})

        if not product_id:
            raise ValidationError({'product_id': 'Requerido.'})
        if quantity < 1:
            raise ValidationError({'quantity': 'Debe ser >= 1.'})

        product = get_object_or_404(Product, pk=product_id, is_active=True, is_published=True)
        variant = None
        has_variants = ProductVariant.objects.filter(product=product, is_active=True).exists()

        if variant_id:
            try:
                variant = ProductVariant.objects.get(pk=variant_id, product=product)
            except ProductVariant.DoesNotExist:
                return Response(
                    {'detail': 'Variante no disponible.', 'codigo_error': 'VARIANT_UNAVAILABLE'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not variant.is_active:
                return Response(
                    {'detail': 'Variante no disponible.', 'codigo_error': 'VARIANT_UNAVAILABLE'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if variant.stock <= 0:
                return Response(
                    {'detail': 'Variante sin stock.', 'codigo_error': 'VARIANT_OUT_OF_STOCK'},
                    status=status.HTTP_409_CONFLICT,
                )
            if quantity > variant.stock:
                return Response(
                    {'detail': 'Variante sin stock suficiente.', 'codigo_error': 'VARIANT_OUT_OF_STOCK'},
                    status=status.HTTP_409_CONFLICT,
                )

        if has_variants and not variant:
            raise ValidationError({'codigo_error': 'VARIANT_REQUIRED',
                                   'variant_id': 'Este producto requiere variante.'})

        order, _, _ = _get_or_create_draft(request)
        try:
            item, created_item = add_item_to_draft(
                order, product, variant=variant, quantity=quantity)
        except DraftOrderError as exc:
            if exc.codigo_error == 'OUT_OF_STOCK':
                return Response(
                    {'detail': 'Producto sin stock.', 'codigo_error': 'OUT_OF_STOCK'},
                    status=status.HTTP_409_CONFLICT,
                )
            raise ValidationError({'codigo_error': exc.codigo_error,
                                   'quantity': 'Stock insuficiente.'})

        resp_status = status.HTTP_201_CREATED if created_item else status.HTTP_200_OK
        resp = Response(DraftCartSerializer(_prefetch_draft(order)).data, status=resp_status)
        if not request.user.is_authenticated:
            resp['X-Cart-Token'] = str(order.cart_token)
        return resp


class CartItemDetailView(APIView):
    """
    PATCH  /api/v1/cart/items/<item_id>/ — actualizar cantidad (UC-CART-02)
    DELETE /api/v1/cart/items/<item_id>/ — eliminar ítem (UC-CART-03)
    """
    permission_classes = [AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'cart'

    @extend_schema(summary='Actualizar cantidad de ítem (UC-CART-02)', tags=['cart'],
                   request=UpdateItemSerializer,
                   responses={200: DraftCartSerializer,
                              400: error_response('Datos inválidos'),
                              404: error_response('Item no encontrado')})
    def patch(self, request, pk):
        order, _, _ = _get_or_create_draft(request)
        qty = request.data.get('quantity')
        if qty is None:
            raise ValidationError({'quantity': 'Requerido.'})
        try:
            qty = int(qty)
        except (ValueError, TypeError):
            raise ValidationError({'quantity': 'Debe ser un entero valido.'})
        if qty < 1:
            raise ValidationError({'quantity': 'Debe ser >= 1.'})
        try:
            update_draft_item_quantity(order, pk, qty)
        except DraftOrderError as exc:
            if exc.codigo_error == 'ITEM_NOT_FOUND':
                raise NotFound({'detail': 'Item no encontrado.',
                                'codigo_error': 'ITEM_NOT_FOUND'})
            raise ValidationError({'codigo_error': exc.codigo_error,
                                   'quantity': 'Stock insuficiente.'})
        return Response(DraftCartSerializer(_prefetch_draft(order)).data)

    @extend_schema(summary='Eliminar ítem del carrito (UC-CART-03)', tags=['cart'],
                   responses={200: DraftCartSerializer})
    def delete(self, request, pk):
        order, _, _ = _get_or_create_draft(request)
        try:
            remove_draft_item(order, pk)
        except DraftOrderError:
            raise NotFound({'detail': 'Item no encontrado.',
                            'codigo_error': 'ITEM_NOT_FOUND'})
        return Response(DraftCartSerializer(_prefetch_draft(order)).data)


class CartSaveView(APIView):
    """POST /api/v1/cart/save/ — UC-CART-05 guardar carrito."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='[DEPRECATED → /api/v2/cart/snapshots/] Guardar carrito para después (UC-CART-05)',
        deprecated=True,
        tags=['cart'],
        request=None,
        responses={200: inline_serializer(
            'CartSaveResponse',
            {'detail': serializers.CharField(),
             'saved_count': serializers.IntegerField()}),
            400: error_response('El carrito está vacío')},
    )
    def post(self, request):
        order, _, _ = _get_or_create_draft(request)
        items = order.items.select_related('product', 'variant').all()
        if not items.exists():
            raise ValidationError({'detail': 'El carrito está vacío.', 'codigo_error': 'EMPTY_CART'})

        saved_count = items.count()
        with transaction.atomic():
            saved, _ = SavedCart.objects.get_or_create(user=request.user)
            saved.items.all().delete()
            for item in items:
                SavedCartItem.objects.create(
                    saved_cart=saved,
                    product=item.product,
                    quantity=item.quantity,
                    price_at_save=item.unit_price,
                )

        return Response({'detail': 'Carrito guardado.', 'saved_count': saved_count})


class CartMergeView(APIView):
    """POST /api/v1/cart/merge/ — UC-CART-06 fusionar carrito anónimo."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='[DEPRECATED → /api/v2/cart/merges/] Fusionar carrito anónimo con cuenta autenticada (UC-CART-06)',
        deprecated=True,
        tags=['cart'],
        request=MergeCartSerializer,
        responses={200: DraftCartSerializer,
                   400: error_response('cart_token requerido')},
    )
    def post(self, request):
        token = request.data.get('cart_token')
        if not token:
            raise ValidationError({'cart_token': 'Requerido.'})

        order, skipped = merge_draft_orders(request.user, token)
        resp_data = DraftCartSerializer(_prefetch_draft(order)).data
        if skipped:
            resp_data['merge_skipped'] = skipped
        return Response(resp_data)


class CartVoucherView(APIView):
    """
    POST   /api/v1/cart/voucher/ — UC-CART-04 aplicar voucher al carrito.
    DELETE /api/v1/cart/voucher/ — quitar voucher del carrito.
    """
    permission_classes = [AllowAny]
    # H-CICLO22-03: throttle dedicado para el endpoint de aplicar voucher.
    # Sin throttle específico el endpoint, al retornar VOUCHER_NOT_FOUND,
    # revelaba existencia de códigos y habilitaba enumeración brute-force.
    # El scope 'voucher_apply' (20/hour anón) limita la ventana de ataque
    # a <1 intento cada 3 minutos para clientes no autenticados.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope   = 'voucher_apply'

    @extend_schema(
        summary='Aplicar voucher al carrito (UC-CART-04)',
        tags=['cart'],
        request=inline_serializer('CartVoucherApplyRequest', {
            'code': serializers.CharField(),
        }),
        responses={200: DraftCartSerializer,
                   400: error_response('Voucher inválido o no aplicable'),
                   409: error_response('Voucher ya utilizado')},
    )
    def post(self, request):
        code = (request.data.get('code') or '').strip().upper()
        if not code:
            raise ValidationError({'code': 'Requerido.'})

        order, _, _ = _get_or_create_draft(request)
        # H-CICLO112-01: el check-then-act corre atómico con
        # select_for_update dentro del servicio.
        try:
            voucher, discount, cart_total = apply_voucher_to_draft(
                order, code,
                request.user if request.user.is_authenticated else None)
        except DraftOrderError as exc:
            if exc.codigo_error == 'VOUCHER_ALREADY_APPLIED':
                return Response({
                    'detail': 'El carrito ya tiene un voucher aplicado. Elimínelo primero.',
                    'codigo_error': 'VOUCHER_ALREADY_APPLIED',
                }, status=409)
            raise ValidationError({'detail': str(exc),
                                   'codigo_error': exc.codigo_error})

        return Response({
            **DraftCartSerializer(_prefetch_draft(order)).data,
            'voucher_code': voucher.code,
            'voucher_discount': str(discount),
            'total_after_discount': str(cart_total - discount),
        })

    @extend_schema(
        summary='Quitar voucher del carrito',
        tags=['cart'],
        responses={200: DraftCartSerializer, 400: None},
    )
    def delete(self, request):
        order, _, _ = _get_or_create_draft(request)
        try:
            remove_voucher_from_draft(order)
        except DraftOrderError as exc:
            raise ValidationError({'detail': str(exc),
                                   'codigo_error': exc.codigo_error})
        return Response(DraftCartSerializer(_prefetch_draft(order)).data)
