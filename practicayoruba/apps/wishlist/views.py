"""Views — apps.wishlist (Sprint 14)."""
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from .models import WishlistItem
from apps.cart.views import _get_or_create_cart
from apps.cart.models import CartItem


# ─── Pagination ─────────────────────────────────────────────

class WishlistPagination(PageNumberPagination):
    page_size             = 12
    page_size_query_param = 'page_size'
    max_page_size         = 50

    def get_paginated_response(self, data, total_items=None, items_out_of_stock=0):
        return Response({
            'count':              self.page.paginator.count,
            'next':               self.get_next_link(),
            'previous':           self.get_previous_link(),
            'total_items':        total_items if total_items is not None else self.page.paginator.count,
            'items_out_of_stock': items_out_of_stock,
            'results':            data,
        })


# ─── Serializers ────────────────────────────────────────────

class WishlistItemSerializer(serializers.ModelSerializer):
    """
    UC-WISH-02 response shape (T-104 D-09).
    Nested product dict aligned to UI contract (product.name/slug/image/base_price).
    availability as string enum: IN_STOCK | OUT_OF_STOCK.
    price_dropped + price_drop_percent for rebaja badge.
    """
    product            = serializers.SerializerMethodField()
    variant_label      = serializers.SerializerMethodField()
    availability       = serializers.SerializerMethodField()
    current_price      = serializers.SerializerMethodField()
    price_dropped      = serializers.SerializerMethodField()
    price_drop_percent = serializers.SerializerMethodField()

    class Meta:
        model  = WishlistItem
        fields = [
            'id', 'product', 'variant_label',
            'price_at_add', 'current_price',
            'availability', 'price_dropped', 'price_drop_percent',
            'created_at',
        ]

    def get_product(self, obj):
        request = self.context.get('request')
        p = obj.product
        first_img = p.images.order_by('order').first()
        image_url = None
        if first_img:
            try:
                image_url = (
                    request.build_absolute_uri(first_img.image.url)
                    if request else first_img.image.url
                )
            except (ValueError, AttributeError):
                pass
        return {
            'id':         p.pk,
            'name':       p.name,
            'slug':       p.slug,
            'image':      image_url,
            'base_price': str(p.price),
        }

    def get_variant_label(self, obj):
        return obj.variant.option.label if obj.variant else None

    def get_availability(self, obj):
        return 'IN_STOCK' if obj.is_available else 'OUT_OF_STOCK'

    def get_current_price(self, obj):
        return str(obj.current_price)

    def get_price_dropped(self, obj):
        return obj.current_price < obj.price_at_add

    def get_price_drop_percent(self, obj):
        if obj.price_at_add and obj.current_price < obj.price_at_add:
            return int((1 - obj.current_price / obj.price_at_add) * 100)
        return 0


# ─── Views ────────────────────────────────────────────────

class WishlistView(APIView):
    """
    GET  /api/v1/wishlist/ — ver lista de deseos (UC-WISH-02)
    POST /api/v1/wishlist/ — agregar producto (UC-WISH-01)
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = WishlistItemSerializer

    @extend_schema(
        summary='Ver lista de deseos',
        tags=['wishlist'],
        parameters=[
            OpenApiParameter(
                'availability', OpenApiTypes.STR,
                description='Filtrar: IN_STOCK | OUT_OF_STOCK',
            ),
            OpenApiParameter('page', OpenApiTypes.INT, description='Numero de pagina'),
        ],
        responses={200: WishlistItemSerializer(many=True)},
    )
    def get(self, request):
        items = list(
            WishlistItem.objects
            .filter(user=request.user)
            .select_related('product', 'variant__option')
        )

        # D-05 UC-WISH-02: filtro disponibilidad (UI sends ?availability=)
        availability_filter = request.query_params.get('availability', '')
        if availability_filter == 'IN_STOCK':
            items = [i for i in items if i.is_available]
        elif availability_filter == 'OUT_OF_STOCK':
            items = [i for i in items if not i.is_available]

        total_items        = len(items)
        items_out_of_stock = sum(1 for i in items if not i.is_available)

        paginator = WishlistPagination()
        page = paginator.paginate_queryset(items, request, view=self)
        serializer = WishlistItemSerializer(
            page if page is not None else items,
            many=True,
            context={'request': request},
        )

        if page is not None:
            return paginator.get_paginated_response(
                serializer.data,
                total_items=total_items,
                items_out_of_stock=items_out_of_stock,
            )
        return Response({
            'count':              total_items,
            'next':               None,
            'previous':           None,
            'total_items':        total_items,
            'items_out_of_stock': items_out_of_stock,
            'results':            serializer.data,
        })

    @extend_schema(
        summary='Agregar producto a lista de deseos',
        tags=['wishlist'],
        responses={
            201: WishlistItemSerializer,
            409: OpenApiResponse(
                description='Producto ya en la lista (PRODUCT_ALREADY_IN_WISHLIST).'
            ),
        },
    )
    def post(self, request):
        product_id = request.data.get('product_id')
        variant_id = request.data.get('variant_id')
        if not product_id:
            raise ValidationError({'product_id': 'Requerido.'})

        product = get_object_or_404(Product, pk=product_id, is_active=True, is_published=True)
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)

        # D-07: price_at_add = Product.base_price (product.price), not variant price.
        price = product.price

        # DEC-DOC-007: si hay fila soft-deleted, reactivar en lugar de crear duplicado.
        existing = WishlistItem.all_objects.filter(
            user=request.user, product=product, variant=variant,
        ).first()
        if existing is not None:
            if existing.is_deleted:
                existing.is_deleted   = False
                existing.deleted_at   = None
                existing.price_at_add = price
                existing.save(update_fields=[
                    'is_deleted', 'deleted_at', 'price_at_add', 'updated_at',
                ])
                return Response(
                    WishlistItemSerializer(existing, context={'request': request}).data,
                    status=201,
                )
            # D-06: producto ya activo en wishlist → 409 Conflict (DEC-DOC-008 loud).
            return Response(
                {'detail': 'El producto ya esta en tu lista de deseos.',
                 'codigo_error': 'PRODUCT_ALREADY_IN_WISHLIST'},
                status=409,
            )

        try:
            item = WishlistItem.objects.create(
                user=request.user, product=product, variant=variant,
                price_at_add=price,
            )
        except IntegrityError:
            return Response(
                {'detail': 'El producto ya esta en tu lista de deseos.',
                 'codigo_error': 'PRODUCT_ALREADY_IN_WISHLIST'},
                status=409,
            )

        return Response(
            WishlistItemSerializer(item, context={'request': request}).data,
            status=201,
        )


class WishlistItemDetailView(APIView):
    """DELETE /api/v1/wishlist/<pk>/ — eliminar item (UC-WISH-02)."""
    permission_classes = [IsAuthenticated]

    def _get_item(self, request, pk):
        return get_object_or_404(WishlistItem, pk=pk, user=request.user)

    @extend_schema(
        summary='Eliminar item de lista de deseos',
        responses={204: None},
        tags=['wishlist'],
    )
    def delete(self, request, pk):
        self._get_item(request, pk).delete()
        return Response(status=204)


class WishlistMoveToCartView(APIView):
    """POST /api/v1/wishlist/<pk>/move-to-cart/ — UC-WISH-03."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Mover producto de wishlist al carrito',
        tags=['wishlist'],
        responses={
            200: OpenApiResponse(
                description='Item movido. Retorna {wishlist_item_id, cart_item_id, moved_at}.',
            ),
            409: OpenApiResponse(
                description='Producto sin stock (PRODUCT_OUT_OF_STOCK).',
            ),
        },
    )
    def post(self, request, pk):
        item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
        if not item.is_available:
            return Response(
                {'detail': 'Este producto no esta disponible.',
                 'codigo_error': 'PRODUCT_OUT_OF_STOCK'},
                status=status.HTTP_409_CONFLICT,
            )

        cart, _, _ = _get_or_create_cart(request)
        unit_price = item.current_price

        with transaction.atomic():
            existing_cart_item = CartItem.objects.filter(
                cart=cart, variant=item.variant, product=item.product,
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

        # D-01 (DEFERRED): remove_from_wishlist → keep_in_wishlist rename + inversion
        # pendiente ADR. Happy path coincide por accidente (ambos default = remover).
        remove = request.data.get('remove_from_wishlist', True)
        if remove:
            item.delete()

        # D-06 UC-WISH-03: compact response per PARTE 7C.3 spec.
        return Response({
            'wishlist_item_id': int(pk),
            'cart_item_id':     cart_item.pk,
            'moved_at':         timezone.now().isoformat(),
        }, status=200)
