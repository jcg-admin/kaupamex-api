"""
Views — apps.orders (Sprint 14)
UC-ORD-01: Crear Orden desde Carrito (Checkout)
"""
import uuid
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.models import Cart, CartItem
from apps.cart.views import _get_or_create_cart
from apps.inventory.services import InventoryService, InsufficientStockError
from apps.settings_app.models import SiteSettings, ShippingMethod

from .models import Order, OrderItem, OrderValue, OrderAddress
from .serializers import CheckoutSerializer, OrderSerializer


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
