"""
Views — apps.chartsize

Sprint 9 — UC-CHT-01, UC-CHT-02, UC-CHT-03, UC-CHT-04
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse
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

class ProductVariantAdminViewSet(ModelViewSet):
    """
    GET    /api/v1/admin/products/<product_pk>/variants/
    POST   /api/v1/admin/products/<product_pk>/variants/
    GET    /api/v1/admin/products/<product_pk>/variants/<pk>/
    PATCH  /api/v1/admin/products/<product_pk>/variants/<pk>/
    DELETE /api/v1/admin/products/<product_pk>/variants/<pk>/

    UC-CHT-03: CRUD de variantes.
    UC-CHT-04: precio diferenciado via price_override.
    Proteccion de ordenes: TODO Sprint 12.
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
        Soft delete: is_active=False.
        Sprint 12: verificar CartItems activos antes de desactivar.
        TODO Sprint 18: verificar ordenes activas (VARIANTE_CON_ORDENES).
        """
        # H-S12-006: protección contra CartItems activos
        active_cart_items = instance.cart_items.count()
        if active_cart_items > 0:
            from rest_framework.exceptions import ValidationError
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
        instance.save(update_fields=['is_active', 'stock'])

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
        instance.is_active = False
        instance.save(update_fields=['is_active'])

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
