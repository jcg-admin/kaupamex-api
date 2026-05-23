"""
Views — apps.chartsize (P-04 / Sprint 7)

UC-CHT-01: Ver tallas disponibles por producto (público)
UC-CHT-02: Editar variante de talla/precio (admin)
UC-CHT-03: Gestionar tipos de variante (admin)
UC-CHT-04: Ajustar precio individual de variante (admin)
"""
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from apps.catalogue.models import Product
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
            product = Product.objects.get(pk=product_id)
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
                   responses={204: None})
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


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
        return super().destroy(request, *args, **kwargs)


class VariantPriceAdminView(APIView):
    """
    PATCH /api/v1/admin/variants/<pk>/price/ — UC-CHT-04.
    Adjust the price_override of a variant.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Ajustar precio de variante (UC-CHT-04)',
        tags=['variants'],
        responses={200: ProductVariantAdminSerializer, 400: None, 404: None},
    )
    def patch(self, request, pk):
        try:
            variant = ProductVariant.objects.get(pk=pk)
        except ProductVariant.DoesNotExist:
            raise NotFound({
                'detail': 'Variante no encontrada.',
                'codigo_error': 'VARIANT_NOT_FOUND',
            })

        price_override = request.data.get('price_override')
        if price_override is None:
            raise ValidationError({
                'detail': 'price_override es requerido.',
                'codigo_error': 'PRICE_REQUIRED',
            })

        variant.price_override = price_override
        variant.save(update_fields=['price_override'])

        return Response(ProductVariantAdminSerializer(variant).data)
