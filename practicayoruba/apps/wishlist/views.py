"""Views — apps.wishlist (Sprint 14)."""
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
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


class WishlistProductSerializer(ModelSerializer):
    """Nested product info for wishlist items (D-09 UC-WISH-02)."""
    base_price = SerializerMethodField()
    image_url  = SerializerMethodField()

    class Meta:
        model  = Product
        fields = ['id', 'name', 'slug', 'base_price', 'image_url']

    def get_base_price(self, obj):
        return str(obj.price)

    def get_image_url(self, obj):
        for img in obj.images.all():
            if img.is_cover and img.image:
                try:
                    return img.image.url
                except Exception:
                    pass
        return None


class WishlistItemSerializer(ModelSerializer):
    product            = WishlistProductSerializer(read_only=True)
    variant_label      = SerializerMethodField()
    current_price      = SerializerMethodField()
    price_changed      = SerializerMethodField()
    availability       = SerializerMethodField()
    price_dropped      = SerializerMethodField()
    price_drop_percent = SerializerMethodField()

    class Meta:
        model  = WishlistItem
        fields = ['id', 'product', 'variant_label',
                  'price_at_add', 'current_price', 'price_changed',
                  'availability', 'price_dropped', 'price_drop_percent',
                  'created_at']

    def get_variant_label(self, obj):
        return obj.variant.option.label if obj.variant else None

    def get_current_price(self, obj):
        return str(obj.current_price)

    def get_price_changed(self, obj):
        return obj.price_changed

    def get_availability(self, obj):
        return 'IN_STOCK' if obj.is_available else 'OUT_OF_STOCK'

    def get_price_dropped(self, obj):
        return obj.current_price < obj.price_at_add

    def get_price_drop_percent(self, obj):
        if obj.price_at_add <= 0:
            return 0
        drop = (obj.price_at_add - obj.current_price) / obj.price_at_add * 100
        return max(0, round(float(drop)))


class WishlistView(APIView):
    """
    GET  /api/v1/wishlist/ — ver lista de deseos (UC-WISH-02)
    POST /api/v1/wishlist/ — agregar producto (UC-WISH-01)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = WishlistItemSerializer

    @extend_schema(summary='Ver lista de deseos', tags=['wishlist'],
                   responses={200: WishlistItemSerializer(many=True)})
    def get(self, request):
        # D-05 UC-WISH-02: paginated response + availability filter
        all_qs = (WishlistItem.objects
                  .filter(user=request.user)
                  .select_related('product', 'variant__option')
                  .prefetch_related('product__images'))
        all_items = list(all_qs)
        total_items = len(all_items)
        items_out_of_stock = sum(1 for i in all_items if not i.is_available)

        avail_filter = request.query_params.get('availability')
        if avail_filter == 'IN_STOCK':
            results = [i for i in all_items if i.is_available]
        elif avail_filter == 'OUT_OF_STOCK':
            results = [i for i in all_items if not i.is_available]
        else:
            results = all_items

        return Response({
            'total_items': total_items,
            'items_out_of_stock': items_out_of_stock,
            'results': WishlistItemSerializer(results, many=True).data,
        })

    @extend_schema(summary='Agregar producto a lista de deseos', tags=['wishlist'],
                   responses={201: WishlistItemSerializer, 409: None})
    def post(self, request):
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id')
        if not product_id:
            raise ValidationError({'product_id': 'Requerido.'})

        product = get_object_or_404(Product, pk=product_id, is_active=True, is_published=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)

        # D-07 UC-WISH-01: price_at_add = Product.base_price (flujo principal UC)
        price = product.price

        # DEC-DOC-007: reactivar fila soft-deleted si existe
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
            # D-06 UC-WISH-01: producto activo ya en wishlist → 409 (DEC-DOC-008)
            return Response(
                {'detail': 'Este producto ya esta en tu lista de deseos.',
                 'codigo_error': 'PRODUCT_ALREADY_IN_WISHLIST'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            item = WishlistItem.objects.create(
                user=request.user, product=product, variant=variant,
                price_at_add=price,
            )
        except IntegrityError:
            return Response(
                {'detail': 'Este producto ya esta en tu lista de deseos.',
                 'codigo_error': 'PRODUCT_ALREADY_IN_WISHLIST'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(WishlistItemSerializer(item).data, status=201)


class WishlistItemDetailView(APIView):
    """DELETE /api/v1/wishlist/<pk>/ — eliminar item (UC-WISH-02)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Eliminar item de lista de deseos',
                   responses={204: None}, tags=['wishlist'])
    def delete(self, request, pk):
        get_object_or_404(WishlistItem, pk=pk, user=request.user).delete()
        return Response(status=204)


class WishlistMoveToCartView(APIView):
    """POST /api/v1/wishlist/<pk>/move-to-cart/ — UC-WISH-03."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Mover producto de wishlist al carrito',
        tags=['wishlist'],
        responses={200: None, 409: None},
    )
    def post(self, request, pk):
        item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
        if not item.is_available:
            # UC-WISH-03 EX-01 + PARTE 7.3
            return Response(
                {'detail': 'Este producto no esta disponible.',
                 'codigo_error': 'PRODUCT_OUT_OF_STOCK'},
                status=status.HTTP_409_CONFLICT,
            )

        cart, _, _ = _get_or_create_cart(request)
        unit_price = item.current_price

        with transaction.atomic():
            existing_cart_item = CartItem.objects.filter(
                cart=cart, variant=item.variant,
                product=item.product,
            ).first()
            if existing_cart_item:
                existing_cart_item.quantity  += 1
                existing_cart_item.unit_price = unit_price
                existing_cart_item.save(update_fields=['quantity', 'unit_price'])
                cart_item = existing_cart_item
            else:
                cart_item = CartItem.objects.create(
                    cart=cart, product=item.product, variant=item.variant,
                    quantity=1, unit_price=unit_price,
                )

        # D-01 UC-WISH-03: keep_in_wishlist (positive semantics, default False).
        # Resuelve 3-way drift: RST mantener_en_lista / UI keep_in_wishlist / API remove_from_wishlist.
        keep = request.data.get('keep_in_wishlist', False)
        if not keep:
            item.delete()

        # D-06 UC-WISH-03: compact response per UC PARTE 7C.3
        return Response({
            'wishlist_item_id': item.pk,
            'cart_item_id': cart_item.pk,
            'moved_at': timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)
