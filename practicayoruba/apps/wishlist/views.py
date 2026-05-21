"""Views — apps.wishlist (Sprint 14)."""
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer, SerializerMethodField
from rest_framework.views import APIView
from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from .models import WishlistItem
from apps.cart.views import _get_or_create_cart
from apps.cart.models import CartItem
from apps.cart.serializers import CartSerializer



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
    serializer_class = WishlistItemSerializer

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

        # DEC-DOC-007: si hay una fila soft-deleted con el mismo
        # (user, product, variant), reactivarla en lugar de crear duplicado.
        existing = WishlistItem.all_objects.filter(
            user=request.user, product=product, variant=variant,
        ).first()
        if existing is not None:
            if existing.is_deleted:
                existing.is_deleted = False
                existing.deleted_at = None
                existing.price_at_add = price
                existing.save(update_fields=[
                    'is_deleted', 'deleted_at', 'price_at_add', 'updated_at',
                ])
                return Response(WishlistItemSerializer(existing).data, status=201)
            return Response(WishlistItemSerializer(existing).data, status=200)

        try:
            item = WishlistItem.objects.create(
                user=request.user, product=product, variant=variant,
                price_at_add=price,
            )
        except IntegrityError:
            item = WishlistItem.objects.get(
                user=request.user, product=product, variant=variant)
            return Response(WishlistItemSerializer(item).data, status=200)

        return Response(WishlistItemSerializer(item).data, status=201)


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
    serializer_class = WishlistItemSerializer

    @extend_schema(
        summary='Mover producto de wishlist al carrito',
        tags=['wishlist'],
    )
    def post(self, request, pk):
        item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
        if not item.is_available:
            # UC-WISH-03 EX-01 + PARTE 7.3 (T-104 D-05 SPLIT chica):
            # producto sin stock o inactivo -> HTTP 409 state conflict
            # con codigo_error PRODUCT_OUT_OF_STOCK (alineado al UC).
            # Antes raise ValidationError -> DRF 400 generico, codigo
            # PRODUCT_UNAVAILABLE no documentado en UC.
            return Response(
                {'detail': 'Este producto no esta disponible.',
                 'codigo_error': 'PRODUCT_OUT_OF_STOCK'},
                status=status.HTTP_409_CONFLICT,
            )

        # Reutilizar la lógica de agregar al carrito (H-S14-006)

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

        return Response(CartSerializer(cart).data, status=200)
