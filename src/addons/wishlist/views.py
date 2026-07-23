"""Views — addons.wishlist (Sprint 14)."""
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_field, inline_serializer
from rest_framework import status
from rest_framework.exceptions import ValidationError
from addons.authz.permissions import CapabilityRequiredMixin
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer, SerializerMethodField
from rest_framework.views import APIView
from addons.catalogue.models import Product
from addons.chartsize.models import ProductVariant
from addons.website_sale_wishlist.models import WishlistItem
from addons.cart.views import _get_or_create_draft
from addons.orders.services import DraftOrderError, add_item_to_draft
from config.schema import error_response
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

    @extend_schema_field(OpenApiTypes.STR)
    def get_variant_label(self, obj):
        return obj.variant.option.label if obj.variant else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_current_price(self, obj):
        return str(obj.current_price)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_price_dropped(self, obj):
        return obj.current_price < obj.price_at_add

    @extend_schema_field(OpenApiTypes.INT)
    def get_price_drop_percent(self, obj):
        if obj.price_at_add and obj.current_price < obj.price_at_add:
            pct = (1 - obj.current_price / obj.price_at_add) * 100
            return round(float(pct))
        return 0

    @extend_schema_field(OpenApiTypes.STR)
    def get_availability(self, obj):
        return 'IN_STOCK' if obj.is_available else 'OUT_OF_STOCK'

    @extend_schema_field(OpenApiTypes.STR)
    def get_product_name(self, obj):
        return obj.product.name

    @extend_schema_field(OpenApiTypes.STR)
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

    @extend_schema_field(OpenApiTypes.STR)
    def get_category_name(self, obj):
        first = obj.product.categories.order_by('id').first()
        return first.name if first else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_orisha_name(self, obj):
        # El modelo Product no tiene campo orisha; se retorna None para
        # que la UI omita la etiqueta silenciosamente via &&.
        return None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_available(self, obj):
        return obj.is_available

    @extend_schema_field(OpenApiTypes.INT)
    def get_stock(self, obj):
        return obj.product.stock


class WishlistView(CapabilityRequiredMixin, APIView):
    """
    GET  /api/v1/wishlist/ — ver lista de deseos (UC-WISH-02)
    POST /api/v1/wishlist/ — agregar producto (UC-WISH-01)
    """
    required_capability = 'account.wishlist'

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
                   request=inline_serializer('WishlistAddRequest', {
                       'product_id': drf_serializers.IntegerField(),
                       'variant_id': drf_serializers.IntegerField(required=False),
                   }),
                   responses={201: WishlistItemSerializer,
                              400: error_response('Datos inválidos'),
                              409: error_response('El producto ya está en la lista')})
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
                return Response(WishlistItemSerializer(existing).data,
                                status=status.HTTP_201_CREATED)
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

        return Response(WishlistItemSerializer(item).data,
                        status=status.HTTP_201_CREATED)


class WishlistItemDetailView(CapabilityRequiredMixin, APIView):
    """
    DELETE /api/v1/wishlist/<pk>/ — eliminar item (UC-WISH-02)
    """
    required_capability = 'account.wishlist'

    def _get_item(self, request, pk):
        return get_object_or_404(WishlistItem, pk=pk, user=request.user)

    @extend_schema(summary='Eliminar item de lista de deseos',
                   responses={204: None}, tags=['wishlist'])
    def delete(self, request, pk):
        self._get_item(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WishlistMoveToCartView(CapabilityRequiredMixin, APIView):
    """POST /api/v1/wishlist/<pk>/move-to-cart/ — UC-WISH-03."""
    required_capability = 'account.wishlist'

    @extend_schema(
        summary='[DEPRECATED → /api/v2/wishlist/<pk>/cart-transfers/] Mover producto de wishlist al carrito',
        deprecated=True,
        tags=['wishlist'],
        request=inline_serializer('WishlistMoveToCartRequest', {
            'remove_from_wishlist': drf_serializers.BooleanField(
                required=False, default=True),
        }),
        responses={200: None,
                   404: error_response('Item no encontrado'),
                   409: error_response('Producto no disponible')},
    )
    def post(self, request, pk):
        item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
        if not item.is_available:
            return Response(
                {'detail': 'Este producto no está disponible.',
                 'codigo_error': 'PRODUCT_OUT_OF_STOCK'},
                status=status.HTTP_409_CONFLICT,
            )

        order, _, _ = _get_or_create_draft(request)

        remove = request.data.get('remove_from_wishlist', True)

        # S3 cart→order→sale: el carrito es el Order(DRAFT); el servicio
        # hace el get_or_create + merge de cantidad con guard de stock.
        with transaction.atomic():
            try:
                draft_item, _ = add_item_to_draft(
                    order, item.product, variant=item.variant, quantity=1)
            except DraftOrderError as exc:
                return Response(
                    {'detail': str(exc), 'codigo_error': exc.codigo_error},
                    status=status.HTTP_409_CONFLICT,
                )
            cart_item_id = draft_item.pk

            if remove:
                item.delete()

        return Response({
            'wishlist_item_id': pk,
            'cart_item_id': cart_item_id,
            'moved_at': timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)


class WishlistAggregateView(CapabilityRequiredMixin, APIView):
    """
    UC-WISH-04 (H-08): agregacion de wishlists para marketing (admin).

    Cuenta, por producto, cuantas veces aparece en listas de deseos y cuantos
    usuarios distintos lo desean. Solo agregados **anonimos**: no expone la
    identidad de los compradores (BR-013). El manager por defecto de
    WishlistItem excluye los soft-deleted.
    """
    required_capability = 'users.view'

    @extend_schema(
        summary='Agregado de wishlist para marketing (admin)',
        tags=['admin-wishlist'],
    )
    def get(self, request):
        rows = (
            WishlistItem.objects
            .values('product_id', 'product__name')
            .annotate(
                times_wishlisted=Count('id'),
                distinct_users=Count('user', distinct=True),
            )
            .order_by('-times_wishlisted', 'product__name')
        )
        data = [
            {
                'product_id':       r['product_id'],
                'name':             r['product__name'],
                'times_wishlisted': r['times_wishlisted'],
                'distinct_users':   r['distinct_users'],
            }
            for r in rows
        ]
        return Response({'results': data, 'count': len(data)})
