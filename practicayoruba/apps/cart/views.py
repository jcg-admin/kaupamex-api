"""
Views — apps.cart (Sprint 6)

UC-CART-01: Ver carrito activo
UC-CART-02: Agregar ítem al carrito
UC-CART-03: Eliminar ítem del carrito
UC-CART-04: Aplicar voucher al carrito
UC-CART-05: Guardar carrito para después
UC-CART-06: Sincronizar carrito anónimo con cuenta
"""
from decimal import Decimal
from uuid import uuid4
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from apps.voucher.models import Voucher, VoucherUsage
from config.schema import error_response
from .models import Cart, CartItem, SavedCart, SavedCartItem
from .serializers import (
    AddItemSerializer, CartSerializer, MergeCartSerializer, SavedCartSerializer,
    UpdateItemSerializer,
)




def _get_or_create_cart(request):
    """
    Devuelve (cart, created, is_authenticated).
    - Autenticado: busca/crea Cart(user=request.user).
    - Anónimo: busca/crea Cart(token=X-Cart-Token header).
    """
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        return cart, created, True
    token = request.META.get('HTTP_X_CART_TOKEN')
    if not token:
        token = str(uuid4())
        created = True
    else:
        created = False
    cart, _ = Cart.objects.get_or_create(cart_token=token)
    return cart, created, False


def _prefetch_cart(cart):
    """
    Re-fetches the cart with prefetch_related to avoid N+1 queries when
    CartSerializer iterates cart.items and accesses product.name/slug/sku
    and variant.option.label.  CartItemSerializer touches:
      - item.product.name, .slug, .sku  → select_related('product')
      - item.variant.option.label        → select_related('variant__option')
      - item.variant.sku                 → select_related('variant')
    Without this re-fetch every CartSerializer(cart).data call fires
    1 + 3 × len(items) extra queries (N+1).
    H-CICLO46-01.
    """
    return (
        Cart.objects
        .prefetch_related('items__product', 'items__variant__option')
        .get(pk=cart.pk)
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
        responses={200: CartSerializer},
    )
    def get(self, request):
        cart, _, _ = _get_or_create_cart(request)
        return Response(CartSerializer(_prefetch_cart(cart)).data)

    @extend_schema(
        summary='Agregar ítem al carrito (UC-CART-02)',
        tags=['cart'],
        request=AddItemSerializer,
        responses={200: CartSerializer,
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

        # H-CICLO121-01: CartView.post() lacked any stock check — a client
        # could add arbitrary quantities via POST /api/v1/cart/ without the
        # guard present in CartItemListView.post(). Validate stock before
        # entering the atomic block and again inside it (double-check pattern)
        # to handle concurrent requests.
        available = variant.stock if variant else product.stock
        if available is not None and available <= 0:
            return Response(
                {'detail': 'Producto sin stock.', 'codigo_error': 'OUT_OF_STOCK'},
                status=status.HTTP_409_CONFLICT,
            )
        if available is not None and quantity > available:
            raise ValidationError({'codigo_error': 'INSUFFICIENT_STOCK',
                                   'quantity': 'Stock insuficiente.'})

        unit_price = variant.effective_price() if variant else product.price

        cart, _, _ = _get_or_create_cart(request)
        with transaction.atomic():
            item, created_item = CartItem.objects.get_or_create(
                cart=cart, product=product, variant=variant,
                defaults={'quantity': quantity, 'unit_price': unit_price},
            )
            if not created_item:
                new_qty = item.quantity + quantity
                avail = variant.stock if variant else product.stock
                if avail is not None and new_qty > avail:
                    raise ValidationError({'codigo_error': 'INSUFFICIENT_STOCK',
                                           'quantity': 'Stock insuficiente.'})
                item.quantity = new_qty
                item.unit_price = unit_price
                item.save(update_fields=['quantity', 'unit_price', 'updated_at'])

        return Response(CartSerializer(_prefetch_cart(cart)).data)

    @extend_schema(summary='Vaciar carrito (UC-CART-03)', tags=['cart'],
                   responses={204: None})
    def delete(self, request):
        cart, _, _ = _get_or_create_cart(request)
        cart.items.all().delete()
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
                   responses={200: CartSerializer})
    def get(self, request):
        cart, _, _ = _get_or_create_cart(request)
        return Response(CartSerializer(_prefetch_cart(cart)).data)

    @extend_schema(summary='Agregar ítem al carrito (UC-CART-02)', tags=['cart'],
                   request=AddItemSerializer,
                   responses={201: CartSerializer, 200: CartSerializer,
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

        available = variant.stock if variant else product.stock
        if available is not None and quantity > available:
            raise ValidationError({'codigo_error': 'INSUFFICIENT_STOCK',
                                   'quantity': 'Stock insuficiente.'})

        unit_price = variant.effective_price() if variant else product.price

        cart, _, _ = _get_or_create_cart(request)
        with transaction.atomic():
            item, created_item = CartItem.objects.get_or_create(
                cart=cart, product=product, variant=variant,
                defaults={'quantity': quantity, 'unit_price': unit_price},
            )
            if not created_item:
                new_qty = item.quantity + quantity
                avail = variant.stock if variant else product.stock
                if avail is not None and new_qty > avail:
                    raise ValidationError({'codigo_error': 'INSUFFICIENT_STOCK',
                                           'quantity': 'Stock insuficiente.'})
                item.quantity = new_qty
                item.unit_price = unit_price
                item.save(update_fields=['quantity', 'unit_price', 'updated_at'])

        resp_status = status.HTTP_201_CREATED if created_item else status.HTTP_200_OK
        resp = Response(CartSerializer(_prefetch_cart(cart)).data, status=resp_status)
        if not request.user.is_authenticated:
            resp['X-Cart-Token'] = str(cart.cart_token)
        return resp


class CartItemDetailView(APIView):
    """
    PATCH  /api/v1/cart/items/<item_id>/ — actualizar cantidad (UC-CART-02)
    DELETE /api/v1/cart/items/<item_id>/ — eliminar ítem (UC-CART-03)
    """
    permission_classes = [AllowAny]
    throttle_classes   = [ScopedRateThrottle]
    throttle_scope     = 'cart'

    def _get_item(self, request, pk):
        cart, _, _ = _get_or_create_cart(request)
        try:
            return CartItem.objects.get(pk=pk, cart=cart)
        except CartItem.DoesNotExist:
            raise NotFound({'detail': 'Item no encontrado.', 'codigo_error': 'ITEM_NOT_FOUND'})

    @extend_schema(summary='Actualizar cantidad de ítem (UC-CART-02)', tags=['cart'],
                   request=UpdateItemSerializer,
                   responses={200: CartSerializer,
                              400: error_response('Datos inválidos'),
                              404: error_response('Item no encontrado')})
    def patch(self, request, pk):
        item = self._get_item(request, pk)
        qty  = request.data.get('quantity')
        if qty is None:
            raise ValidationError({'quantity': 'Requerido.'})
        try:
            qty = int(qty)
        except (ValueError, TypeError):
            raise ValidationError({'quantity': 'Debe ser un entero valido.'})
        if qty < 1:
            raise ValidationError({'quantity': 'Debe ser >= 1.'})
        stock = item.variant.stock if item.variant else item.product.stock
        if stock is not None and qty > stock:
            raise ValidationError({'codigo_error': 'INSUFFICIENT_STOCK',
                                   'quantity': 'Stock insuficiente.'})
        item.quantity = qty
        item.save(update_fields=['quantity', 'updated_at'])
        cart, _, _ = _get_or_create_cart(request)
        return Response(CartSerializer(_prefetch_cart(cart)).data)

    @extend_schema(summary='Eliminar ítem del carrito (UC-CART-03)', tags=['cart'],
                   responses={200: CartSerializer})
    def delete(self, request, pk):
        item = self._get_item(request, pk)
        item.delete()
        cart, _, _ = _get_or_create_cart(request)
        return Response(CartSerializer(_prefetch_cart(cart)).data)


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
        cart, _, _ = _get_or_create_cart(request)
        items = cart.items.select_related('product', 'variant').all()
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
            cart.items.all().delete()

        return Response({'detail': 'Carrito guardado.', 'saved_count': saved_count})


class CartMergeView(APIView):
    """POST /api/v1/cart/merge/ — UC-CART-06 fusionar carrito anónimo."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='[DEPRECATED → /api/v2/cart/merges/] Fusionar carrito anónimo con cuenta autenticada (UC-CART-06)',
        deprecated=True,
        tags=['cart'],
        request=MergeCartSerializer,
        responses={200: CartSerializer,
                   400: error_response('cart_token requerido')},
    )
    def post(self, request):
        token = request.data.get('cart_token')
        if not token:
            raise ValidationError({'cart_token': 'Requerido.'})

        try:
            anon_cart = Cart.objects.get(cart_token=token, user__isnull=True)
        except Cart.DoesNotExist:
            auth_cart, _ = Cart.objects.get_or_create(user=request.user)
            return Response(CartSerializer(_prefetch_cart(auth_cart)).data)

        auth_cart, _ = Cart.objects.get_or_create(user=request.user)

        skipped = []
        with transaction.atomic():
            for anon_item in anon_cart.items.select_related('product', 'variant').all():
                # H-CICLO20-02: validar disponibilidad de stock antes de
                # fusionar cada ítem del carrito anónimo. Ítems sin stock
                # suficiente se omiten (no se fusionan) y se reportan al
                # caller para que el UI informe al usuario.
                available = (
                    anon_item.variant.stock
                    if anon_item.variant
                    else anon_item.product.stock
                )
                if available is not None and available <= 0:
                    skipped.append({
                        'product_id': anon_item.product.pk,
                        'product_name': anon_item.product.name,
                        'reason': 'OUT_OF_STOCK',
                    })
                    continue

                existing = CartItem.objects.filter(
                    cart=auth_cart,
                    product=anon_item.product,
                    variant=anon_item.variant,
                ).first()
                if existing:
                    new_qty = existing.quantity + anon_item.quantity
                    if available is not None and new_qty > available:
                        new_qty = available
                    existing.quantity = new_qty
                    existing.unit_price = anon_item.unit_price
                    existing.save(update_fields=['quantity', 'unit_price', 'updated_at'])
                else:
                    merge_qty = anon_item.quantity
                    if available is not None and merge_qty > available:
                        merge_qty = available
                    CartItem.objects.create(
                        cart=auth_cart,
                        product=anon_item.product,
                        variant=anon_item.variant,
                        quantity=merge_qty,
                        unit_price=anon_item.unit_price,
                    )
            anon_cart.delete()

        resp_data = CartSerializer(_prefetch_cart(auth_cart)).data
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
        responses={200: CartSerializer,
                   400: error_response('Voucher inválido o no aplicable'),
                   409: error_response('Voucher ya utilizado')},
    )
    def post(self, request):
        code = (request.data.get('code') or '').strip().upper()
        if not code:
            raise ValidationError({'code': 'Requerido.'})

        try:
            voucher = Voucher.objects.get(code=code)
        except Voucher.DoesNotExist:
            raise ValidationError({
                'detail': 'El voucher no existe.',
                'codigo_error': 'VOUCHER_NOT_FOUND',
            })

        cart, _, _ = _get_or_create_cart(request)

        # H-CICLO112-01: wrap the check-then-act sequence in a single
        # atomic block with select_for_update() on the cart to prevent
        # two concurrent POST requests from both passing the
        # VoucherUsage.exists() guard and the cart.voucher_id is None
        # guard before either commits, resulting in one voucher applied
        # twice (both writes succeed, last writer wins silently).
        # select_for_update serializes concurrent requests for the same
        # cart row so only one proceeds through the guards at a time.
        with transaction.atomic():
            cart = Cart.objects.select_for_update().get(pk=cart.pk)

            cart_total = sum(
                item.unit_price * item.quantity for item in cart.items.all()
            )

            error_code = voucher.validate_for_cart(cart_total, request.user)
            if error_code:
                raise ValidationError({
                    'detail': f'Voucher no aplicable: {error_code}',
                    'codigo_error': error_code,
                })

            # Single-use-per-user enforcement (DEC-BC-10)
            if request.user.is_authenticated:
                if VoucherUsage.objects.filter(user=request.user, voucher=voucher).exists():
                    raise ValidationError({
                        'detail': 'Ya has utilizado este voucher.',
                        'codigo_error': 'VOUCHER_ALREADY_USED',
                    })

            # If cart already has a voucher, reject with 409 (DEC-BC-20)
            if cart.voucher_id is not None:
                return Response({
                    'detail': 'El carrito ya tiene un voucher aplicado. Elímínelo primero.',
                    'codigo_error': 'VOUCHER_ALREADY_APPLIED',
                }, status=409)

            cart.voucher = voucher
            cart.save(update_fields=['voucher', 'updated_at'])

        discount = voucher.calculate_discount(cart_total)
        return Response({
            **CartSerializer(_prefetch_cart(cart)).data,
            'voucher_code': voucher.code,
            'voucher_discount': str(discount),
            'total_after_discount': str(cart_total - discount),
        })

    @extend_schema(
        summary='Quitar voucher del carrito',
        tags=['cart'],
        responses={200: CartSerializer, 400: None},
    )
    def delete(self, request):
        cart, _, _ = _get_or_create_cart(request)
        if cart.voucher_id is None:
            raise ValidationError({
                'detail': 'El carrito no tiene voucher aplicado.',
                'codigo_error': 'NO_ACTIVE_VOUCHER',
            })
        cart.voucher = None
        cart.save(update_fields=['voucher', 'updated_at'])
        return Response(CartSerializer(_prefetch_cart(cart)).data)
