"""Views — apps.wishlist (Sprint 14)."""
from decimal import Decimal
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer, SerializerMethodField
from rest_framework.views import APIView

from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from .models import WishlistItem


class WishlistItemSerializer(ModelSerializer):
    product_name  = SerializerMethodField()
    product_slug  = SerializerMethodField()
    variant_label = SerializerMethodField()
    current_price = SerializerMethodField()
    price_changed = SerializerMethodField()
    is_available  = SerializerMethodField()

    class Meta:
        model  = WishlistItem
        fields = ['id', 'product_name', 'product_slug', 'variant_label',
                  'price_at_add', 'current_price', 'price_changed',
                  'is_available', 'created_at']

    def get_product_name(self, obj):  return obj.product.name
    def get_product_slug(self, obj):  return obj.product.slug
    def get_variant_label(self, obj): return obj.variant.option.label if obj.variant else None
    def get_current_price(self, obj): return str(obj.current_price)
    def get_price_changed(self, obj): return obj.price_changed
    def get_is_available(self, obj):  return obj.is_available


class WishlistView(APIView):
    """
    GET  /api/v1/wishlist/ — ver lista de deseos (UC-WISH-02)
    POST /api/v1/wishlist/ — agregar producto (UC-WISH-01)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Ver lista de deseos', tags=['wishlist'])
    def get(self, request):
        items = (WishlistItem.objects
                 .filter(user=request.user)
                 .select_related('product', 'variant__option'))
        return Response(WishlistItemSerializer(items, many=True).data)

    @extend_schema(summary='Agregar producto a lista de deseos', tags=['wishlist'])
    def post(self, request):
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id')
        if not product_id:
            raise ValidationError({'product_id': 'Requerido.'})

        product = get_object_or_404(Product, pk=product_id, is_active=True, is_published=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)

        price = variant.effective_price() if variant else product.price

        try:
            item, created = WishlistItem.objects.get_or_create(
                user=request.user, product=product, variant=variant,
                defaults={'price_at_add': price},
            )
        except IntegrityError:
            item = WishlistItem.objects.get(
                user=request.user, product=product, variant=variant)
            created = False

        return Response(WishlistItemSerializer(item).data,
                        status=201 if created else 200)


class WishlistItemDetailView(APIView):
    """
    DELETE /api/v1/wishlist/<pk>/ — eliminar item (UC-WISH-02)
    POST   /api/v1/wishlist/<pk>/move-to-cart/ — mover al carrito (UC-WISH-03)
    """
    permission_classes = [IsAuthenticated]

    def _get_item(self, request, pk):
        return get_object_or_404(WishlistItem, pk=pk, user=request.user)

    @extend_schema(summary='Eliminar item de lista de deseos',
                   responses={204: None}, tags=['wishlist'])
    def delete(self, request, pk):
        self._get_item(request, pk).delete()
        return Response(status=204)


class WishlistMoveToCartView(APIView):
    """POST /api/v1/wishlist/<pk>/move-to-cart/ — UC-WISH-03."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Mover producto de wishlist al carrito',
        tags=['wishlist'],
    )
    def post(self, request, pk):
        item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
        if not item.is_available:
            raise ValidationError({
                'detail': 'Este producto no está disponible.',
                'codigo_error': 'PRODUCTO_NO_DISPONIBLE',
            })

        # Reutilizar la lógica de agregar al carrito (H-S14-006)
        from apps.cart.views import _get_or_create_cart
        from apps.cart.models import CartItem
        from django.db import transaction

        cart, _, _ = _get_or_create_cart(request)
        unit_price = item.current_price

        with transaction.atomic():
            existing = CartItem.objects.filter(
                cart=cart, variant=item.variant,
                product=item.product,
            ).first()
            if existing:
                existing.quantity  += 1
                existing.unit_price = unit_price
                existing.save(update_fields=['quantity', 'unit_price'])
            else:
                CartItem.objects.create(
                    cart=cart, product=item.product, variant=item.variant,
                    quantity=1, unit_price=unit_price,
                )

        remove = request.data.get('remove_from_wishlist', True)
        if remove:
            item.delete()

        from apps.cart.serializers import CartSerializer
        return Response(CartSerializer(cart).data, status=200)
