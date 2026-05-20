"""
Views — apps.chartsize

Sprint 9 — UC-CHT-01, UC-CHT-02, UC-CHT-03, UC-CHT-04
"""
from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.catalogue.models import Product
from .models import VariantType, VariantOption, ProductVariant
from .serializers import (
    ProductVariantSerializer,
    ProductVariantAdminSerializer,
    VariantTypeAdminSerializer,
)


# =============================================================================
# UC-CHT-01 / UC-CHT-02 — Vista pública de variante (validación)
# =============================================================================

class VariantDetailView(APIView):
    """
    GET /api/v1/catalogue/<slug>/variants/<pk>/

    Retorna el estado actual de una variante especifica (stock, precio).
    Usado por el frontend para confirmar disponibilidad antes de agregar
    al carrito (UC-CHT-02). El agregar al carrito es Sprint 12.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Validar estado de variante',
        description=(
            'Retorna stock, precio efectivo y disponibilidad de una variante. '
            'Usado antes de agregar al carrito. UC-CHT-02 (validacion).'
        ),
        responses={200: ProductVariantSerializer, 404: None},
        tags=['catalogue'],
    )
    def get(self, request, slug, pk):
        product = get_object_or_404(
            Product, slug=slug, is_active=True, is_published=True
        )
        variant = get_object_or_404(
            ProductVariant, pk=pk, product=product, is_active=True
        )
        return Response(ProductVariantSerializer(variant).data)


# =============================================================================
# UC-CHT-03 y UC-CHT-04 — CRUD admin de variantes
# =============================================================================

@extend_schema_view(
    list=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    create=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    retrieve=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
        OpenApiParameter('id', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    update=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
        OpenApiParameter('id', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    partial_update=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
        OpenApiParameter('id', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    destroy=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
        OpenApiParameter('id', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
)
class ProductVariantAdminViewSet(ModelViewSet):
    """
    GET    /api/v1/admin/products/<product_pk>/variants/
    POST   /api/v1/admin/products/<product_pk>/variants/
    GET    /api/v1/admin/products/<product_pk>/variants/<pk>/
    PATCH  /api/v1/admin/products/<product_pk>/variants/<pk>/
    DELETE /api/v1/admin/products/<product_pk>/variants/<pk>/

    UC-CHT-03: CRUD de variantes.
    UC-CHT-04: precio diferenciado via price_override.
    Proteccion CartItems activos: implementada en Sprint 12.
    Proteccion ordenes activas: resuelto en Sprint 19 con ActiveOrder proxy.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = ProductVariantAdminSerializer
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def _get_product(self):
        return get_object_or_404(Product, pk=self.kwargs['product_pk'])

    def get_queryset(self):
        product = self._get_product()
        return (
            ProductVariant.objects
            .filter(product=product)
            .select_related('option', 'option__variant_type')
            .order_by('option__order', 'option__label')
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['product'] = self._get_product()
        return ctx

    def perform_create(self, serializer):
        """
        La variante se vincula a un VariantOption.
        El admin debe enviar option_id (ID de una VariantOption ya creada).
        """
        serializer.save()

    def perform_destroy(self, instance):
        """
        Soft delete (DEC-DOC-007).

        Marca la variante como borrada logicamente (``is_deleted=True`` +
        ``deleted_at``) y, ademas, desactiva la visibilidad de negocio
        (``is_active=False``, ``stock=0``) — ambos campos coexisten:
        uno modela la regla de negocio (UC-CHT-03), el otro la politica
        de retencion historica.

        Sprint 12: verificar CartItems activos antes de desactivar.
        H-ORD-005: verificar ActiveOrders antes de desactivar (Sprint 19).
        """
        from django.utils import timezone
        # H-ORD-005: protección contra órdenes activas
        from apps.orders.proxy_models import ActiveOrder
        if ActiveOrder.objects.filter(items__variant=instance).exists():
            raise ValidationError({
                'detail': 'No se puede eliminar esta variante porque tiene órdenes activas.',
                'codigo_error': 'VARIANTE_CON_ORDENES_ACTIVAS',
            })
        # H-S12-006: protección contra CartItems activos
        active_cart_items = instance.cart_items.count()
        if active_cart_items > 0:
            raise ValidationError({
                'detail': (
                    f'Esta variante tiene {active_cart_items} item(s) en carritos activos. '
                    f'Desactivarla los dejaría sin stock. '
                    f'Espera a que esos carritos expiren o sean vaciados.'
                ),
                'codigo_error': 'VARIANTE_CON_ITEMS_EN_CARRITO',
            })
        instance.is_active = False
        instance.stock     = 0
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=[
            'is_active', 'stock', 'is_deleted', 'deleted_at',
        ])

    @extend_schema(summary='Listar variantes del producto', tags=['admin-catalogue'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Crear variante',
        description='Requiere option_id de un VariantOption ya creado.',
        tags=['admin-catalogue'],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary='Editar variante (stock, precio diferenciado, is_active)',
        tags=['admin-catalogue'],
    )
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Desactivar variante (soft delete)',
        responses={204: None},
        tags=['admin-catalogue'],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


@extend_schema_view(
    list=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    create=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    retrieve=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
        OpenApiParameter('id', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    update=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
        OpenApiParameter('id', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    partial_update=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
        OpenApiParameter('id', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
    destroy=extend_schema(parameters=[
        OpenApiParameter('product_pk', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
        OpenApiParameter('id', OpenApiTypes.INT,
                         OpenApiParameter.PATH),
    ]),
)
class VariantTypeAdminViewSet(ModelViewSet):
    """
    GET|POST /api/v1/admin/products/<product_pk>/variant-types/
    PATCH|DELETE /api/v1/admin/products/<product_pk>/variant-types/<pk>/

    UC-CHT-03: gestionar tipos de variante (Tamaño, Presentación, etc.)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = VariantTypeAdminSerializer
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def _get_product(self):
        return get_object_or_404(Product, pk=self.kwargs['product_pk'])

    def get_queryset(self):
        return VariantType.objects.filter(
            product=self._get_product()
        ).prefetch_related('options').order_by('order', 'name')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['product'] = self._get_product()
        return ctx

    def perform_create(self, serializer):
        serializer.save(product=self._get_product())

    def perform_destroy(self, instance):
        """Soft delete (DEC-DOC-007): ``is_deleted`` + visibilidad apagada."""
        from django.utils import timezone
        instance.is_active = False
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=[
            'is_active', 'is_deleted', 'deleted_at',
        ])

    @extend_schema(summary='Listar tipos de variante', tags=['admin-catalogue'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear tipo de variante', tags=['admin-catalogue'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar tipo de variante', tags=['admin-catalogue'])
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


# =============================================================================
# UC-CHT-04 — Differentiated price endpoint
# UI consumes PUT/DELETE /api/v1/admin/variants/<variant_pk>/price/
# =============================================================================

class VariantPriceAdminView(APIView):
    """
    PUT    /api/v1/admin/variants/<variant_pk>/price/  — set price_override
    DELETE /api/v1/admin/variants/<variant_pk>/price/  — clear price_override

    UC-CHT-04 (FR-CHT-04.02): differentiated price per variant.
    Returns the updated variant serialized with ProductVariantAdminSerializer.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_variant(self, variant_pk):
        return get_object_or_404(ProductVariant, pk=variant_pk)

    @extend_schema(
        summary='Set differentiated price on a variant',
        request={'application/json': {'type': 'object',
                                       'properties': {'price': {'type': 'string'}},
                                       'required': ['price']}},
        responses={200: ProductVariantAdminSerializer, 400: None, 404: None},
        tags=['variants'],
    )
    def put(self, request, variant_pk):
        variant = self._get_variant(variant_pk)
        raw = request.data.get('price', None)
        if raw is None or raw == '':
            raise ValidationError({'price': 'This field is required.'})
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError({'price': 'Invalid decimal value.'})
        if value <= Decimal('0'):
            raise ValidationError({
                'price': 'The differentiated price must be greater than zero.',
            })
        variant.price_override = value
        variant.save(update_fields=['price_override', 'updated_at'])
        return Response(ProductVariantAdminSerializer(variant).data)

    @extend_schema(
        summary='Clear differentiated price (fall back to product base price)',
        responses={200: ProductVariantAdminSerializer, 404: None},
        tags=['variants'],
    )
    def delete(self, request, variant_pk):
        variant = self._get_variant(variant_pk)
        if variant.price_override is not None:
            variant.price_override = None
            variant.save(update_fields=['price_override', 'updated_at'])
        return Response(ProductVariantAdminSerializer(variant).data)
