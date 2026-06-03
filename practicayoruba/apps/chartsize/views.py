"""
Views — apps.chartsize (P-04 / Sprint 7)

UC-CHT-01: Ver tallas disponibles por producto (público)
UC-CHT-02: Editar variante de talla/precio (admin)
UC-CHT-03: Gestionar tipos de variante (admin)
UC-CHT-04: Ajustar precio individual de variante (admin)
"""
from decimal import Decimal as _Decimal, InvalidOperation

from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from apps.cart.models import CartItem
from apps.catalogue.models import Product
from apps.orders.models import Order, OrderItem
from config.schema import error_response
from .models import ProductVariant, VariantType
from .serializers import (
    ProductVariantAdminSerializer,
    ProductVariantPublicSerializer,
    VariantTypeSerializer,
)




class VariantDetailView(APIView):
    """
    GET /api/v1/products/<product_id>/variants/ — UC-CHT-01.
    Returns the list of variants for a product (public).
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Listar variantes del producto (UC-CHT-01)',
        tags=['variants'],
        responses={200: ProductVariantPublicSerializer(many=True)},
    )
    def get(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id, is_active=True, is_published=True)
        except Product.DoesNotExist:
            raise NotFound({
                'detail': 'Producto no encontrado.',
                'codigo_error': 'PRODUCT_NOT_FOUND',
            })
        variants = (
            ProductVariant.objects
            .filter(product=product)
            .select_related('option', 'option__variant_type')
            .order_by('option__variant_type__name', 'option__label')
        )
        return Response(ProductVariantPublicSerializer(variants, many=True).data)


class VariantSingleView(APIView):
    """
    GET /api/v1/catalogue/<slug>/variants/<pk>/ — UC-CHT-01 validate single variant.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Validar variante individual del producto (UC-CHT-01)',
        tags=['variants'],
        responses={200: ProductVariantPublicSerializer, 404: None},
    )
    def get(self, request, slug, pk):
        try:
            product = Product.objects.get(slug=slug, is_active=True, is_published=True)
        except Product.DoesNotExist:
            raise NotFound({
                'detail': 'Producto no encontrado.',
                'codigo_error': 'PRODUCT_NOT_FOUND',
            })
        try:
            variant = ProductVariant.objects.select_related(
                'option', 'option__variant_type'
            ).get(pk=pk, product=product)
        except ProductVariant.DoesNotExist:
            raise NotFound({
                'detail': 'Variante no encontrada.',
                'codigo_error': 'VARIANT_NOT_FOUND',
            })
        return Response(ProductVariantPublicSerializer(variant).data)


class ProductVariantAdminViewSet(ModelViewSet):
    """
    Admin CRUD for product variants — UC-CHT-02.

    GET    /api/v1/admin/variants/           list (filterable by ?product=<id>)
    POST   /api/v1/admin/variants/           create
    GET    /api/v1/admin/variants/<pk>/      detail
    PATCH  /api/v1/admin/variants/<pk>/      update
    DELETE /api/v1/admin/variants/<pk>/      delete
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = ProductVariantAdminSerializer
    queryset           = ProductVariant.objects.all().select_related(
        'product', 'option', 'option__variant_type'
    )
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        # H-CICLO99-01: product_pk comes from the URL path kwarg when the
        # ViewSet is mounted at /api/v1/admin/products/<product_pk>/variants/.
        # Previously only ?product= query param was checked, so the path-based
        # filter was silently ignored and the list action returned ALL variants
        # across all products when accessed via the canonical nested URL.
        product_pk = self.kwargs.get('product_pk')
        if product_pk:
            qs = qs.filter(product_id=product_pk)
            return qs
        product_id = self.request.query_params.get('product')
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs

    @extend_schema(summary='Listar variantes (admin)', tags=['variants'],
                   responses={200: ProductVariantAdminSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear variante (admin)', tags=['variants'],
                   responses={201: ProductVariantAdminSerializer})
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar variante (admin)', tags=['variants'],
                   responses={200: ProductVariantAdminSerializer})
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(summary='Eliminar variante (admin)', tags=['variants'],
                   responses={204: None, 400: None})
    def destroy(self, request, *args, **kwargs):
        variant = self.get_object()
        if CartItem.objects.filter(variant=variant).exists():
            raise ValidationError({
                'codigo_error': 'VARIANT_WITH_CART_ITEMS',
                'detail': 'No se puede eliminar una variante con ítems en carritos activos.',
            })
        # H-ORD-005: proteger variante si tiene OrderItems en órdenes activas
        active_statuses = [
            Order.STATUS_PENDING, Order.STATUS_PROCESSING,
            Order.STATUS_IN_PREPARATION, Order.STATUS_SHIPPED,
        ]
        if OrderItem.objects.filter(
            variant=variant, order__status__in=active_statuses
        ).exists():
            raise ValidationError({
                'codigo_error': 'VARIANT_WITH_ACTIVE_ORDERS',
                'detail': 'No se puede eliminar una variante con órdenes activas.',
            })
        # Soft-delete: deactivate and zero out stock
        variant.is_active = False
        variant.stock = 0
        variant.save(update_fields=['is_active', 'stock', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class VariantTypeAdminViewSet(ModelViewSet):
    """
    Admin CRUD for variant types — UC-CHT-03.

    GET    /api/v1/admin/variant-types/           list
    POST   /api/v1/admin/variant-types/           create
    PATCH  /api/v1/admin/variant-types/<pk>/      update
    DELETE /api/v1/admin/variant-types/<pk>/      delete
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = VariantTypeSerializer
    queryset           = VariantType.objects.all().order_by('name')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        product_pk = self.kwargs.get('product_pk')
        if product_pk:
            qs = qs.filter(product_id=product_pk)
        return qs

    def get_serializer_context(self):
        """H-CICLO27-04: pasar product al contexto del serializer para que
        validate_name() pueda verificar unicidad de nombre por producto y
        devolver ValidationError 400 en lugar de IntegrityError 500."""
        ctx = super().get_serializer_context()
        product_pk = self.kwargs.get('product_pk')
        if product_pk:
            try:
                ctx['product'] = Product.objects.get(pk=product_pk)
            except (Product.DoesNotExist, ValueError):
                pass  # silent OK because el product del contexto es opcional; se valida aguas abajo (400 no 500)
        return ctx

    @extend_schema(summary='Listar tipos de variante (admin)', tags=['variants'],
                   responses={200: VariantTypeSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear tipo de variante (admin)', tags=['variants'],
                   responses={201: VariantTypeSerializer})
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar tipo de variante (admin)', tags=['variants'],
                   responses={200: VariantTypeSerializer})
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(summary='Eliminar tipo de variante (admin)', tags=['variants'],
                   responses={204: None})
    def destroy(self, request, *args, **kwargs):
        # H-CICLO100-01: SoftDeleteModel.delete() marks VariantType as
        # is_deleted=True but does NOT cascade to child VariantOption rows
        # because soft-delete bypasses the DB-level CASCADE constraint.
        # Without this guard, VariantOptions whose variant_type is deleted
        # remain visible (is_deleted=False) as orphans, breaking listing
        # and assignment flows that filter options via the active manager.
        # Solution: soft-delete all child options before deleting the type.
        instance = self.get_object()
        now = timezone.now()
        instance.options.filter(is_deleted=False).update(
            is_deleted=True, deleted_at=now,
        )
        return super().destroy(request, *args, **kwargs)


class VariantPriceAdminView(APIView):
    """
    PUT    /api/v1/admin/variants/<variant_pk>/price/ — UC-CHT-04 set price override.
    DELETE /api/v1/admin/variants/<variant_pk>/price/ — UC-CHT-04 clear price override.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_variant(self, variant_pk):
        try:
            return ProductVariant.objects.get(pk=variant_pk)
        except ProductVariant.DoesNotExist:
            raise NotFound({
                'detail': 'Variante no encontrada.',
                'codigo_error': 'VARIANT_NOT_FOUND',
            })

    @extend_schema(
        summary='Ajustar precio de variante (UC-CHT-04)',
        tags=['variants'],
        request=inline_serializer('VariantPriceRequest', {
            'price': serializers.DecimalField(max_digits=10, decimal_places=2),
        }),
        responses={200: ProductVariantAdminSerializer,
                   400: error_response('Precio inválido'),
                   404: error_response('Variante no encontrada')},
    )
    def put(self, request, variant_pk):
        variant = self._get_variant(variant_pk)
        price = request.data.get('price')
        if price is None:
            raise ValidationError({
                'detail': 'price es requerido.',
                'codigo_error': 'PRICE_REQUIRED',
            })
        try:
            price_decimal = _Decimal(str(price))
        except (InvalidOperation, TypeError):
            raise ValidationError({'price': 'Valor numérico inválido.'})
        if price_decimal <= _Decimal('0'):
            raise ValidationError({'price': 'El precio debe ser mayor que cero.'})

        variant.price_override = price_decimal
        variant.save(update_fields=['price_override', 'updated_at'])

        return Response(ProductVariantAdminSerializer(variant).data)

    @extend_schema(
        summary='Limpiar precio diferenciado de variante (UC-CHT-04)',
        tags=['variants'],
        responses={200: ProductVariantAdminSerializer, 404: None},
    )
    def delete(self, request, variant_pk):
        variant = self._get_variant(variant_pk)
        variant.price_override = None
        variant.save(update_fields=['price_override', 'updated_at'])
        return Response(ProductVariantAdminSerializer(variant).data)

    # Keep PATCH for backwards compatibility
    @extend_schema(
        summary='Ajustar precio de variante (UC-CHT-04, alias PATCH)',
        tags=['variants'],
        request=inline_serializer('VariantPricePatchRequest', {
            'price': serializers.DecimalField(max_digits=10, decimal_places=2),
        }),
        responses={200: ProductVariantAdminSerializer,
                   400: error_response('Precio inválido'),
                   404: error_response('Variante no encontrada')},
    )
    def patch(self, request, variant_pk):
        return self.put(request, variant_pk)
