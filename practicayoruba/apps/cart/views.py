"""
Views — apps.cart (Sprint 12)
UC-CART-01: Agregar Producto al Carrito
UC-CART-02: Ver y Editar Carrito
UC-CART-03: Eliminar Item del Carrito
UC-CART-05: Guardar Carrito para Despues
UC-CART-06: Sincronizar Carrito Anonimo al Autenticar
"""
import logging
import uuid
from decimal import Decimal
from django.db import transaction
from apps.voucher.serializers import ApplyVoucherSerializer
from apps.voucher.models import Voucher
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from apps.inventory.services import InventoryService
from .models import Cart, CartItem, SavedCart, SavedCartItem
from .serializers import CartSerializer, CartItemSerializer, AddItemSerializer, UpdateItemSerializer, MergeCartSerializer, SavedCartItemSerializer


logger = logging.getLogger(__name__)



CART_TOKEN_HEADER = 'HTTP_X_CART_TOKEN'


# =============================================================================
# Helpers de carrito
# =============================================================================

def _get_or_create_cart(request) -> tuple:
    """
    Retorna (cart, is_new, cart_token).
    - Autenticado: busca Cart por user.
    - Anonimo: busca por X-Cart-Token header.
    """
    if request.user and request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        return cart, created, None

    # Anonimo
    raw_token = request.META.get(CART_TOKEN_HEADER, '')
    if raw_token:
        try:
            token = uuid.UUID(str(raw_token))
            cart = Cart.objects.filter(cart_token=token, user__isnull=True).first()
            if cart:
                return cart, False, str(token)
        except (ValueError, AttributeError):
            # Loud-log: cart_token malformado puede indicar manipulacion
            # del cliente. No abortamos (creamos carrito nuevo) pero
            # operaciones debe ver la frecuencia. DEC-DOC-008.
            logger.warning(
                'cart_token malformed value=%r, creating new cart',
                raw_token,
            )

    # Crear carrito anonimo nuevo
    new_token = uuid.uuid4()
    cart = Cart.objects.create(cart_token=new_token, user=None)
    return cart, True, str(new_token)


def _refresh_item_prices(cart: Cart) -> list:
    """
    Actualiza unit_price de cada CartItem al precio vigente.
    Retorna lista de IDs con precio cambiado.
    """
    changed = []
    for item in cart.items.select_related('variant__product', 'product').all():
        current = item.current_price()
        if current != item.unit_price:
            item.unit_price = current
            item.save(update_fields=['unit_price'])
            changed.append(item.pk)
    return changed


# =============================================================================
# UC-CART-02: Ver carrito y editar cantidad
# UC-CART-03: Eliminar item
# =============================================================================

class CartView(APIView):
    """
    GET    /api/v1/cart/ — ver carrito con totales. UC-CART-02.
    DELETE /api/v1/cart/ — vaciar carrito completo.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Ver carrito',
        description=(
            'Retorna el carrito activo con items, subtotales y desglose de totales. '
            'Actualiza unit_price de items si el precio del producto cambio. '
            'Visitantes anonimos: enviar X-Cart-Token header.'
        ),
        parameters=[
            OpenApiParameter('X-Cart-Token', str, location='header',
                             description='Token UUID del carrito anonimo')
        ],
        responses={200: CartSerializer},
        tags=['cart'],
    )
    def get(self, request):
        cart, _, cart_token = _get_or_create_cart(request)
        changed_ids = set(_refresh_item_prices(cart))
        data = CartSerializer(cart, context={'changed_ids': changed_ids, 'request': request}).data
        response = Response(data)
        if cart_token:
            response['X-Cart-Token'] = cart_token
        return response

    @extend_schema(
        summary='Vaciar carrito',
        responses={204: None},
        tags=['cart'],
    )
    def delete(self, request):
        cart, is_new, cart_token = _get_or_create_cart(request)
        if not is_new:
            cart.items.all().delete()
        return Response(status=204)


class CartItemListView(APIView):
    """
    POST /api/v1/cart/items/ — agregar item. UC-CART-01.

    Split de CartItemView (D-032 T-6): el detail view se separo para
    eliminar colisiones de operationId que spectacular emitia cuando
    una sola clase manejaba dos URLs (la URL de lista y la URL de
    detalle).
    """
    permission_classes = [AllowAny]
    serializer_class = CartItemSerializer

    @extend_schema(
        summary='Agregar item al carrito',
        request=AddItemSerializer,
        responses={201: CartSerializer, 200: CartSerializer},
        tags=['cart'],
        operation_id='cart_items_add',
    )
    def post(self, request):
        s = AddItemSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        product_id = s.validated_data['product_id']
        variant_id = s.validated_data.get('variant_id')
        quantity   = s.validated_data['quantity']

        product = get_object_or_404(Product, pk=product_id, is_active=True, is_published=True)

        # Resolver variante
        if variant_id:
            variant = (
                ProductVariant.objects
                .filter(pk=variant_id, product=product, is_active=True)
                .first()
            )
            if variant is None:
                return Response(
                    {
                        'detail': 'La variante solicitada no esta disponible.',
                        'codigo_error': 'VARIANT_UNAVAILABLE',
                    },
                    status=404,
                )
        elif product.variant_types.filter(is_active=True).exists():
            raise ValidationError({
                'variant_id': (
                    'Este producto tiene variantes. '
                    'Debes seleccionar una variante (variant_id).'
                ),
                'codigo_error': 'VARIANT_REQUIRED',
            })
        else:
            variant = None

        # Verificar stock
        available = variant.stock if variant else product.stock
        if available < quantity:
            if variant is not None:
                return Response(
                    {
                        'detail': f'Variante sin stock suficiente. Disponible: {available}.',
                        'codigo_error': 'VARIANT_OUT_OF_STOCK',
                        'available_stock': available,
                    },
                    status=409,
                )
            raise ValidationError({
                'quantity': f'Stock insuficiente. Disponible: {available}.',
                'codigo_error': 'INSUFFICIENT_STOCK',
            })

        unit_price = variant.effective_price() if variant else product.price
        cart, _, cart_token = _get_or_create_cart(request)

        was_new_item = True
        with transaction.atomic():
            # Upsert: si ya existe el item con la misma variante, sumar cantidad
            lookup = {'cart': cart, 'variant': variant} if variant else {'cart': cart, 'product': product, 'variant': None}
            existing = CartItem.objects.filter(**lookup).first()
            if existing:
                was_new_item = False
                new_qty = existing.quantity + quantity
                if new_qty > available:
                    if variant is not None:
                        return Response(
                            {
                                'detail': (
                                    f'Variante sin stock suficiente. Disponible: {available}.'
                                ),
                                'codigo_error': 'VARIANT_OUT_OF_STOCK',
                                'available_stock': available,
                            },
                            status=409,
                        )
                    raise ValidationError({
                        'quantity': f'Stock insuficiente. Disponible: {available}.',
                        'codigo_error': 'INSUFFICIENT_STOCK',
                    })
                existing.quantity   = new_qty
                existing.unit_price = unit_price
                existing.save(update_fields=['quantity', 'unit_price'])
            else:
                CartItem.objects.create(
                    cart=cart, product=product, variant=variant,
                    quantity=quantity, unit_price=unit_price,
                )

        # DEC-BC-02 + DEC-BC-08 (consolidadas): retornar Cart completo con
        # totals (no item suelto). Single contract en todas las cart
        # mutations garantiza que UI nunca calcule totales localmente
        # ni asuma shape. Status 201 si insert, 200 si merge.
        status_code = 201 if was_new_item else 200
        data = CartSerializer(cart, context={'request': request}).data
        response = Response(data, status=status_code)
        if cart_token:
            response['X-Cart-Token'] = cart_token
        return response


class CartItemDetailView(APIView):
    """
    PATCH  /api/v1/cart/items/<pk>/ — editar cantidad. UC-CART-02.
    DELETE /api/v1/cart/items/<pk>/ — eliminar item.   UC-CART-03.

    Split de CartItemView (D-032 T-6).
    """
    permission_classes = [AllowAny]
    serializer_class = CartItemSerializer

    @extend_schema(
        summary='Editar cantidad de item',
        request=UpdateItemSerializer,
        responses={200: CartSerializer},
        tags=['cart'],
        operation_id='cart_items_update',
    )
    def patch(self, request, pk):
        cart, _, _ = _get_or_create_cart(request)
        item = get_object_or_404(CartItem, pk=pk, cart=cart)
        s = UpdateItemSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        new_qty = s.validated_data['quantity']
        available = item.available_stock()
        if new_qty > available:
            raise ValidationError({
                'quantity': f'Stock insuficiente. Disponible: {available}.',
                'codigo_error': 'INSUFFICIENT_STOCK',
            })
        item.quantity = new_qty
        item.save(update_fields=['quantity'])
        # DEC-BC-02 + DEC-BC-08: Cart shape para que UI use setCart
        # consistentemente sin recalcular totales.
        return Response(CartSerializer(cart, context={'request': request}).data)

    @extend_schema(
        summary='Eliminar item del carrito',
        responses={200: CartSerializer},
        tags=['cart'],
        operation_id='cart_items_destroy',
    )
    def delete(self, request, pk):
        cart, _, _ = _get_or_create_cart(request)
        item = get_object_or_404(CartItem, pk=pk, cart=cart)
        item.delete()
        # DEC-BC-02 + DEC-BC-08: DELETE devuelve Cart actualizado
        # (200) en lugar de 204. Sin necesidad de fetch post-mutation
        # para refrescar totals.
        cart.refresh_from_db()
        return Response(CartSerializer(cart, context={'request': request}).data)


# Backwards-compatible alias for any module that imports the
# pre-split class name. urls.py refs go directly to the two new
# classes; this alias only protects accidental imports.
CartItemView = CartItemListView


# =============================================================================
# UC-CART-05: Guardar carrito para después
# =============================================================================

class CartSaveView(APIView):
    """POST /api/v1/cart/save/ — UC-CART-05."""
    permission_classes = [IsAuthenticated]
    serializer_class = SavedCartItemSerializer

    @extend_schema(
        summary='Guardar carrito para después',
        responses={200: SavedCartItemSerializer(many=True)},
        tags=['cart'],
    )
    def post(self, request):
        cart, _, _ = _get_or_create_cart(request)
        items = list(cart.items.select_related('product').all())
        if not items:
            raise ValidationError({'detail': 'El carrito está vacío.', 'codigo_error': 'EMPTY_CART'})

        with transaction.atomic():
            saved, _ = SavedCart.objects.get_or_create(user=request.user)
            # Reemplazar los items guardados anteriores
            saved.items.all().delete()
            for item in items:
                SavedCartItem.objects.create(
                    saved_cart=saved,
                    product=item.product,
                    quantity=item.quantity,
                    price_at_save=item.unit_price,
                )

        return Response({
            'saved_count': len(items),
            'message': f'{len(items)} item(s) guardados para después.',
        })


# =============================================================================
# UC-CART-06: Fusionar carrito anónimo al autenticar
# =============================================================================

class CartMergeView(APIView):
    """
    POST /api/v1/cart/merge/ — UC-CART-06.
    Fusiona el carrito anonimo (identificado por cart_token)
    en el carrito del usuario autenticado.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Fusionar carrito anónimo al autenticar',
        request=MergeCartSerializer,
        responses={200: CartSerializer},
        tags=['cart'],
    )
    def post(self, request):
        s = MergeCartSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        anon_token = s.validated_data['cart_token']

        anon_cart = Cart.objects.filter(cart_token=anon_token, user__isnull=True).first()
        if not anon_cart:
            # No hay carrito anónimo — retornar el carrito del usuario tal cual
            user_cart, _ = Cart.objects.get_or_create(user=request.user)
            return Response(CartSerializer(user_cart).data)

        user_cart, _ = Cart.objects.get_or_create(user=request.user)

        if anon_cart.pk != user_cart.pk:
            user_cart.merge(anon_cart)

        _refresh_item_prices(user_cart)
        return Response(CartSerializer(user_cart).data)


# =============================================================================
# Sprint 13 — UC-CART-04: Aplicar/quitar cupón de descuento
# =============================================================================

class CartVoucherView(APIView):
    """
    POST   /api/v1/cart/voucher/ — aplicar cupón (UC-CART-04)
    DELETE /api/v1/cart/voucher/ — quitar cupón
    """
    permission_classes = [AllowAny]
    serializer_class = CartSerializer

    @extend_schema(
        summary='Aplicar cupón de descuento al carrito',
        description=(
            'Valida el código y lo vincula al carrito. '
            'Retorna el carrito con totales actualizados. '
            'UC-CART-04 (FR-CART-04.01, FR-CART-04.02).'
        ),
        responses={200: CartSerializer},
        tags=['cart'],
    )
    def post(self, request):

        s = ApplyVoucherSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        code = s.validated_data['code'].upper()

        try:
            voucher = Voucher.objects.get(code=code)
        except Voucher.DoesNotExist:
            raise ValidationError({'code': 'Cupón no encontrado.',
                                   'codigo_error': 'VOUCHER_NOT_FOUND'})

        cart, _, cart_token = _get_or_create_cart(request)

        # DEC-BC-20: rechazar si ya hay un voucher aplicado (409).
        if cart.voucher_id:
            return Response(
                {'code': 'Ya hay un cupón aplicado. Elimínalo antes de aplicar otro.',
                 'codigo_error': 'VOUCHER_ALREADY_APPLIED'},
                status=409,
            )

        subtotal = cart.get_subtotal()

        error_code = voucher.validate_for_cart(subtotal, request.user)
        if error_code:
            # voucher.validate_for_cart emite codes EN canonicos; cart mapea
            # a mensaje user-facing y propaga el error_code tal cual al
            # cliente.
            messages = {
                'VOUCHER_INACTIVE':                   'Este cupón no está activo.',
                'VOUCHER_NOT_YET_ACTIVE':             'Este cupón aún no está vigente.',
                'VOUCHER_EXPIRED':                    'Este cupón ha expirado.',
                'VOUCHER_EXHAUSTED':                  'Este cupón ha alcanzado su límite de usos.',
                'MINIMUM_AMOUNT_NOT_REACHED':         f'El carrito debe superar ${voucher.min_order_amount}.',
                'VOUCHER_REQUIRES_AUTHENTICATION':    'Debes iniciar sesión para usar este cupón.',
                'VOUCHER_RESTRICTED_TO_OTHER_EMAIL':  'Este cupón no es válido para tu cuenta.',
            }
            raise ValidationError({
                'code': messages.get(error_code, 'Cupón inválido.'),
                'codigo_error': error_code,
            })

        cart.voucher = voucher
        cart.save(update_fields=['voucher'])

        data = CartSerializer(cart).data
        response = Response(data)
        if cart_token:
            response['X-Cart-Token'] = cart_token
        return response

    @extend_schema(
        summary='Quitar cupón del carrito',
        responses={200: None},
        tags=['cart'],
    )
    def delete(self, request):
        cart, _, cart_token = _get_or_create_cart(request)
        if not cart.voucher_id:
            raise ValidationError({'detail': 'No hay cupón aplicado.',
                                   'codigo_error': 'NO_ACTIVE_VOUCHER'})
        cart.voucher = None
        cart.save(update_fields=['voucher'])
        data = CartSerializer(cart).data
        response = Response(data)
        if cart_token:
            response['X-Cart-Token'] = cart_token
        return response
