"""Views — apps.wishlist (Sprint 14)."""
from decimal import Decimal
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
from rest_framework import serializers as drf_serializers


class WishlistProductNestedSerializer(drf_serializers.ModelSerializer):
    """Compact product info nested inside wishlist item."""
    base_price = drf_serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'base_price']


class WishlistItemSerializer(ModelSerializer):
    """H-CICLO37-03: WishlistPage.jsx accede a campos planos como
    ``product_name``, ``image_url``, ``category_name``, ``orisha_name``,
    ``is_available`` y ``stock``, pero el serializer sólo exponía el
    objeto anidado ``product`` y el string ``availability``. Se agregan
    los campos planos necesarios como SerializerMethodFields para que
    la UI pueda renderizar correctamente sin errores de undefined.
    """

    product       = WishlistProductNestedSerializer(read_only=True)
    variant_label = SerializerMethodField()
    current_price = SerializerMethodField()
    price_dropped = SerializerMethodField()
    price_drop_percent = SerializerMethodField()
    availability  = SerializerMethodField()
    # Flat aliases requeridos por WishlistPage.jsx
    product_name  = SerializerMethodField()
    image_url     = SerializerMethodField()
    category_name = SerializerMethodField()
    orisha_name   = SerializerMethodField()
    is_available  = SerializerMethodField()
    stock         = SerializerMethodField()

    class Meta:
        model  = WishlistItem
        fields = [
            'id', 'product', 'variant_label',
            'price_at_add', 'current_price',
            'price_dropped', 'price_drop_percent',
            'availability', 'created_at',
            'product_name', 'image_url', 'category_name',
            'orisha_name', 'is_available', 'stock',
        ]

    def get_variant_label(self, obj):
        return obj.variant.option.label if obj.variant else None

    def get_current_price(self, obj):
        return str(obj.current_price)

    def get_price_dropped(self, obj):
        return obj.current_price < obj.price_at_add

    def get_price_drop_percent(self, obj):
        if obj.price_at_add and obj.current_price < obj.price_at_add:
            pct = (1 - obj.current_price / obj.price_at_add) * 100
            return round(float(pct))
        return 0

    def get_availability(self, obj):
        return 'IN_STOCK' if obj.is_available else 'OUT_OF_STOCK'

    def get_product_name(self, obj):
        return obj.product.name

    def get_image_url(self, obj):
        request = self.context.get('request')
        cover = obj.product.images.filter(is_cover=True).first()
        if cover is None:
            cover = obj.product.images.first()
        if cover is None:
            return None
        url = cover.image.url
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_category_name(self, obj):
        first = obj.product.categories.order_by('id').first()
        return first.name if first else None

    def get_orisha_name(self, obj):
        # El modelo Product no tiene campo orisha; se retorna None para
        # que la UI omita la etiqueta silenciosamente via &&.
        return None

    def get_is_available(self, obj):
        return obj.is_available

    def get_stock(self, obj):
        return obj.product.stock


class WishlistView(APIView):
    """
    GET  /api/v1/wishlist/ — ver lista de deseos (UC-WISH-02)
    POST /api/v1/wishlist/ — agregar producto (UC-WISH-01)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Ver lista de deseos', tags=['wishlist'],
                   responses={200: WishlistItemSerializer(many=True)})
    def get(self, request):
        qs = (WishlistItem.objects
              .filter(user=request.user)
              .select_related('product', 'variant__option')
              .prefetch_related('product__categories', 'product__images'))

        avail_filter = request.query_params.get('availability')
        if avail_filter:
            all_items = list(qs)
            if avail_filter == 'IN_STOCK':
                qs = [i for i in all_items if i.is_available]
            elif avail_filter == 'OUT_OF_STOCK':
                qs = [i for i in all_items if not i.is_available]
        else:
            qs = list(qs)

        items_out_of_stock = sum(1 for i in qs if not i.is_available)
        data = WishlistItemSerializer(qs, many=True).data
        return Response({
            'results': data,
            'total_items': len(data),
            'items_out_of_stock': items_out_of_stock,
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

        price = product.price

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
            return Response(
                {'detail': 'El producto ya está en la lista de deseos.',
                 'codigo_error': 'PRODUCT_ALREADY_IN_WISHLIST'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            item = WishlistItem.objects.create(
                user=request.user, product=product, variant=variant,
                price_at_add=price,
            )
        except IntegrityError:
            item = WishlistItem.objects.get(
                user=request.user, product=product, variant=variant)
            return Response(
                {'detail': 'El producto ya está en la lista de deseos.',
                 'codigo_error': 'PRODUCT_ALREADY_IN_WISHLIST'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(WishlistItemSerializer(item).data, status=201)


class WishlistItemDetailView(APIView):
    """
    DELETE /api/v1/wishlist/<pk>/ — eliminar item (UC-WISH-02)
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
        responses={200: None},
    )
    def post(self, request, pk):
        item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
        if not item.is_available:
            return Response(
                {'detail': 'Este producto no está disponible.',
                 'codigo_error': 'PRODUCT_OUT_OF_STOCK'},
                status=status.HTTP_409_CONFLICT,
            )

        cart, _, _ = _get_or_create_cart(request)
        unit_price = item.current_price

        remove = request.data.get('remove_from_wishlist', True)

        with transaction.atomic():
            existing = CartItem.objects.select_for_update().filter(
                cart=cart, variant=item.variant,
                product=item.product,
            ).first()
            if existing:
                existing.quantity += 1
                existing.unit_price = unit_price
                existing.save(update_fields=['quantity', 'unit_price', 'updated_at'])
                cart_item_id = existing.pk
            else:
                cart_item = CartItem.objects.create(
                    cart=cart, product=item.product, variant=item.variant,
                    quantity=1, unit_price=unit_price,
                )
                cart_item_id = cart_item.pk

            if remove:
                item.delete()

        return Response({
            'wishlist_item_id': pk,
            'cart_item_id': cart_item_id,
            'moved_at': timezone.now().isoformat(),
        }, status=200)
