"""``main`` — la superficie HTTP de la lista de deseos.

Adaptación de ``odoo19c: website_sale_wishlist/controllers/main.py``
(LGPL-3) a DRF. Correspondencia de operaciones:

=============================================  ==============================
Referencia (rutas ``/shop/wishlist*``)         Aquí (``/api/v2/wishlist/``)
=============================================  ==============================
``add_to_wishlist`` (jsonrpc, dedupe por       ``POST /`` — 201 / 409
``UNIQUE(product_id, partner_id)``)            ``PRODUCT_ALREADY_IN_WISHLIST``
``get_wishlist`` (render de ``current()``)     ``GET /`` — JSON paginable con
                                               filtro ``availability``
``remove_from_wishlist``                       ``DELETE /<pk>/`` — 204
                                               (soft-delete, DEC-DOC-007)
=============================================  ==============================

Lo que la referencia guarda al agregar —el precio del momento
(``price``/``_add_to_wishlist``)— aquí es ``price_at_add``; la fuente es
``lst_price`` (ficha + extra), la misma propiedad que cobra el carrito.

Divergencias deliberadas frente a la fuente:

- **Sin rama anónima.** La referencia admite wishlist de sesión pública
  (``wishlist_ids`` en session) y la migra al partner al loguearse
  (``_check_wishlist_from_session``). Aquí la lista exige la capacidad
  ``account.wishlist`` (fail-closed, DEC-11): la wishlist anónima llegará,
  si llega, con la familia ``website_sale`` y su sesión de tienda.
- **``cart-transfers``** no existe en el controller de la referencia (allá
  el botón llama al cart de ``website_sale``): es la composición de las dos
  operaciones — quitar de la lista + ``add_item_to_draft`` del carrito
  (``sale.services``, donde el carrito ES la ``sale.order`` draft).
"""
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import CapabilityRequiredMixin
from addons.product.models import ProductProduct
from addons.sale.services import (
    DraftOrderError,
    add_item_to_draft,
    get_or_create_draft_order,
)
from addons.website_sale_wishlist.controllers.serializers import (
    WishlistItemSerializer,
)
from addons.website_sale_wishlist.models import WishlistItem
from config.schema import error_response


class WishlistView(CapabilityRequiredMixin, APIView):
    """
    GET  /api/v2/wishlist/ — ver lista de deseos (UC-WISH-02)
    POST /api/v2/wishlist/ — agregar producto (UC-WISH-01)
    """
    required_capability = 'account.wishlist'

    @extend_schema(summary='Ver lista de deseos', tags=['wishlist'],
                   responses={200: WishlistItemSerializer(many=True)})
    def get(self, request):
        # El ``current()`` de la referencia: los items del usuario cuyo
        # producto sigue vendible. La disponibilidad se deriva de
        # ``stock.quant``, así que el filtro se evalúa en Python.
        qs = (WishlistItem.objects
              .filter(user=request.user)
              .select_related('product__product_tmpl__categ'))

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
        data = WishlistItemSerializer(
            qs, many=True, context={'request': request}).data
        return Response({
            'results': data,
            'total_items': len(data),
            'items_out_of_stock': items_out_of_stock,
        })

    @extend_schema(summary='Agregar producto a lista de deseos', tags=['wishlist'],
                   request=inline_serializer('WishlistAddRequest', {
                       'product_id': drf_serializers.IntegerField(),
                   }),
                   responses={201: WishlistItemSerializer,
                              400: error_response('Datos inválidos'),
                              409: error_response('El producto ya está en la lista')})
    def post(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            raise ValidationError({'product_id': 'Requerido.'})

        product = get_object_or_404(ProductProduct, pk=product_id, active=True)
        price = product.lst_price

        existing = WishlistItem.all_objects.filter(
            user=request.user, product=product,
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
                user=request.user, product=product, price_at_add=price,
            )
        except IntegrityError:
            # Carrera contra el UNIQUE(user, product) — el veredicto lo da
            # la BD, igual que el Constraint de la referencia.
            return Response(
                {'detail': 'El producto ya está en la lista de deseos.',
                 'codigo_error': 'PRODUCT_ALREADY_IN_WISHLIST'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(WishlistItemSerializer(item).data,
                        status=status.HTTP_201_CREATED)


class WishlistItemDetailView(CapabilityRequiredMixin, APIView):
    """DELETE /api/v2/wishlist/<pk>/ — eliminar item (UC-WISH-02)."""
    required_capability = 'account.wishlist'

    @extend_schema(summary='Eliminar item de lista de deseos',
                   responses={204: None}, tags=['wishlist'])
    def delete(self, request, pk):
        item = get_object_or_404(WishlistItem, pk=pk, user=request.user)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WishlistMoveToCartView(CapabilityRequiredMixin, APIView):
    """POST /api/v2/wishlist/<pk>/cart-transfers/ — UC-WISH-03."""
    required_capability = 'account.wishlist'

    @extend_schema(
        summary='Mover producto de la lista de deseos al carrito',
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

        order, _ = get_or_create_draft_order(user=request.user)
        remove = request.data.get('remove_from_wishlist', True)

        with transaction.atomic():
            try:
                line, _ = add_item_to_draft(order, item.product, quantity=1)
            except DraftOrderError as exc:
                return Response(
                    {'detail': str(exc), 'codigo_error': exc.codigo_error},
                    status=status.HTTP_409_CONFLICT,
                )
            cart_item_id = line.pk
            if remove:
                item.delete()

        return Response({
            'wishlist_item_id': pk,
            'cart_item_id': cart_item_id,
            'moved_at': timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)


class WishlistAggregateView(CapabilityRequiredMixin, APIView):
    """
    UC-WISH-04 (H-08): agregación de wishlists para marketing (admin).

    Cuenta, por producto, cuántas veces aparece en listas de deseos y
    cuántos usuarios distintos lo desean. Sólo agregados **anónimos**: no
    expone la identidad de los compradores (BR-013). El manager por defecto
    de ``WishlistItem`` excluye los soft-deleted.
    """
    required_capability = 'users.view'

    @extend_schema(
        summary='Agregado de wishlist para marketing (admin)',
        tags=['admin-wishlist'],
        responses={200: inline_serializer('WishlistAggregateResponse', {
            'results': drf_serializers.ListField(
                child=inline_serializer('WishlistAggregateRow', {
                    'product_id': drf_serializers.IntegerField(),
                    'name': drf_serializers.CharField(),
                    'times_wishlisted': drf_serializers.IntegerField(),
                    'distinct_users': drf_serializers.IntegerField(),
                })),
            'count': drf_serializers.IntegerField(),
        })},
    )
    def get(self, request):
        # El nombre vive en la ficha (``product_tmpl``) — en la variante es
        # una propiedad delegada, no una columna consultable.
        rows = (
            WishlistItem.objects
            .values('product_id', 'product__product_tmpl__name')
            .annotate(
                times_wishlisted=Count('id'),
                distinct_users=Count('user', distinct=True),
            )
            .order_by('-times_wishlisted', 'product__product_tmpl__name')
        )
        data = [
            {
                'product_id':       r['product_id'],
                'name':             r['product__product_tmpl__name'],
                'times_wishlisted': r['times_wishlisted'],
                'distinct_users':   r['distinct_users'],
            }
            for r in rows
        ]
        return Response({'results': data, 'count': len(data)})
