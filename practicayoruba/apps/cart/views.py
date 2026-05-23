"""
Views — apps.cart (Sprint 6)

UC-CART-01: Ver carrito activo
UC-CART-02: Agregar ítem al carrito
UC-CART-03: Eliminar ítem del carrito
UC-CART-04: Guardar carrito para después
UC-CART-05: Fusionar carrito anónimo con cuenta
UC-CART-06: Aplicar voucher al carrito
"""
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from apps.voucher.models import Voucher
from .models import Cart, CartItem, SavedCart, SavedCartItem
from .serializers import CartSerializer, SavedCartSerializer




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
        from uuid import uuid4
        token = str(uuid4())
        created = True
    else:
        created = False
    cart, _ = Cart.objects.get_or_create(token=token)
    return cart, created, False


class CartView(APIView):
    """
    GET  /api/v1/cart/  — UC-CART-01 ver carrito activo.
    POST /api/v1/cart/  — UC-CART-02 agregar ítem.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Ver carrito activo (UC-CART-01)',
        tags=['cart'],
        responses={200: CartSerializer},
    )
    def get(self, request):
        cart, _, _ = _get_or_create_cart(request)
        return Response(CartSerializer(cart).data)

    @extend_schema(
        summary='Agregar ítem al carrito (UC-CART-02)',
        tags=['cart'],
        responses={200: CartSerializer, 400: None},
    )
    def post(self, request):
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id')
        quantity   = int(request.data.get('quantity', 1))

        if not product_id:
            raise ValidationError({'product_id': 'Requerido.'})
        if quantity < 1:
            raise ValidationError({'quantity': 'Debe ser >= 1.'})

        product = get_object_or_404(Product, pk=product_id, is_active=True, is_published=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)

        unit_price = variant.effective_price() if variant else product.price

        cart, _, _ = _get_or_create_cart(request)
        with transaction.atomic():
            item, created_item = CartItem.objects.get_or_create(
                cart=cart, product=product, variant=variant,
                defaults={'quantity': quantity, 'unit_price': unit_price},
            )
            if not created_item:
                item.quantity += quantity
                item.unit_price = unit_price
                item.save(update_fields=['quantity', 'unit_price'])

        return Response(CartSerializer(cart).data)


class CartItemListView(APIView):
    """GET /api/v1/cart/items/ — UC-CART-01 alias."""
    permission_classes = [AllowAny]

    @extend_schema(summary='Listar items del carrito', tags=['cart'],
                   responses={200: CartSerializer})
    def get(self, request):
        cart, _, _ = _get_or_create_cart(request)
        return Response(CartSerializer(cart).data)


class CartItemDetailView(APIView):
    """
    PATCH  /api/v1/cart/items/<item_id>/ — actualizar cantidad (UC-CART-02)
    DELETE /api/v1/cart/items/<item_id>/ — eliminar ítem (UC-CART-03)
    """
    permission_classes = [AllowAny]

    def _get_item(self, request, item_id):
        cart, _, _ = _get_or_create_cart(request)
        try:
            return CartItem.objects.get(pk=item_id, cart=cart)
        except CartItem.DoesNotExist:
            raise NotFound({'detail': 'Item no encontrado.', 'codigo_error': 'ITEM_NOT_FOUND'})

    @extend_schema(summary='Actualizar cantidad de ítem (UC-CART-02)', tags=['cart'],
                   responses={200: CartSerializer, 400: None})
    def patch(self, request, item_id):
        item = self._get_item(request, item_id)
        qty  = request.data.get('quantity')
        if qty is None:
            raise ValidationError({'quantity': 'Requerido.'})
        qty = int(qty)
        if qty < 1:
            raise ValidationError({'quantity': 'Debe ser >= 1.'})
        item.quantity = qty
        item.save(update_fields=['quantity'])
        cart, _, _ = _get_or_create_cart(request)
        return Response(CartSerializer(cart).data)

    @extend_schema(summary='Eliminar ítem del carrito (UC-CART-03)', tags=['cart'],
                   responses={200: CartSerializer})
    def delete(self, request, item_id):
        item = self._get_item(request, item_id)
        item.delete()
        cart, _, _ = _get_or_create_cart(request)
        return Response(CartSerializer(cart).data)


class CartSaveView(APIView):
    """POST /api/v1/cart/save/ — UC-CART-04 guardar carrito."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Guardar carrito para después (UC-CART-04)',
        tags=['cart'],
        responses={200: None},
    )
    def post(self, request):
        cart, _, _ = _get_or_create_cart(request)
        items = cart.items.select_related('product', 'variant').all()
        if not items.exists():
            raise ValidationError({'detail': 'El carrito está vacío.', 'codigo_error': 'CART_EMPTY'})

        with transaction.atomic():
            saved, _ = SavedCart.objects.get_or_create(user=request.user)
            saved.items.all().delete()
            for item in items:
                SavedCartItem.objects.create(
                    cart=saved,
                    product=item.product,
                    variant=item.variant,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                )
            cart.items.all().delete()

        return Response({'detail': 'Carrito guardado.'})


class CartMergeView(APIView):
    """POST /api/v1/cart/merge/ — UC-CART-05 fusionar carrito anónimo."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Fusionar carrito anónimo con cuenta autenticada (UC-CART-05)',
        tags=['cart'],
        responses={200: CartSerializer},
    )
    def post(self, request):
        token = request.data.get('cart_token')
        if not token:
            raise ValidationError({'cart_token': 'Requerido.'})

        try:
            anon_cart = Cart.objects.get(token=token, user__isnull=True)
        except Cart.DoesNotExist:
            raise NotFound({'detail': 'Carrito anónimo no encontrado.', 'codigo_error': 'ANON_CART_NOT_FOUND'})

        auth_cart, _ = Cart.objects.get_or_create(user=request.user)

        with transaction.atomic():
            for anon_item in anon_cart.items.select_related('product', 'variant').all():
                existing = CartItem.objects.filter(
                    cart=auth_cart,
                    product=anon_item.product,
                    variant=anon_item.variant,
                ).first()
                if existing:
                    existing.quantity += anon_item.quantity
                    existing.unit_price = anon_item.unit_price
                    existing.save(update_fields=['quantity', 'unit_price'])
                else:
                    CartItem.objects.create(
                        cart=auth_cart,
                        product=anon_item.product,
                        variant=anon_item.variant,
                        quantity=anon_item.quantity,
                        unit_price=anon_item.unit_price,
                    )
            anon_cart.delete()

        return Response(CartSerializer(auth_cart).data)


class CartVoucherView(APIView):
    """POST /api/v1/cart/voucher/ — UC-CART-06 aplicar voucher al carrito."""
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Aplicar voucher al carrito (UC-CART-06)',
        tags=['cart'],
        responses={200: CartSerializer, 400: None},
    )
    def post(self, request):
        code = (request.data.get('code') or '').strip().upper()
        if not code:
            raise ValidationError({'code': 'Requerido.'})

        try:
            voucher = Voucher.objects.get(code=code, is_active=True)
        except Voucher.DoesNotExist:
            raise ValidationError({
                'detail': 'El voucher no es válido o ha expirado.',
                'codigo_error': 'VOUCHER_INVALID',
            })

        if not voucher.is_valid():
            raise ValidationError({
                'detail': 'El voucher no es válido o ha expirado.',
                'codigo_error': 'VOUCHER_EXPIRED',
            })

        cart, _, _ = _get_or_create_cart(request)
        cart_total = sum(
            item.unit_price * item.quantity for item in cart.items.all()
        )

        if voucher.minimum_purchase and cart_total < voucher.minimum_purchase:
            raise ValidationError({
                'detail': f'El carrito debe superar {voucher.minimum_purchase} para aplicar este voucher.',
                'codigo_error': 'MINIMUM_NOT_MET',
            })

        if voucher.discount_type == Voucher.TYPE_PERCENTAGE:
            discount = (cart_total * voucher.discount_value / Decimal('100')).quantize(Decimal('0.01'))
        else:
            discount = min(voucher.discount_value, cart_total)

        return Response({
            **CartSerializer(cart).data,
            'voucher_code': voucher.code,
            'voucher_discount': str(discount),
            'total_after_discount': str(cart_total - discount),
        })
