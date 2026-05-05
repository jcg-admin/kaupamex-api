"""
Views — apps.catalogue
Sprint 4 — UC-CAT-01: Ver Catálogo
Sprint 5 — UC-CAT-02: Ver Detalle de Producto
          UC-CAT-03 / UC-SRCH-01: Buscar Productos (FULLTEXT MySQL)
          UC-CAT-03-EXT: Filtros Avanzados sobre búsqueda
"""
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Product
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    ProductSearchSerializer,
)


class CataloguePagination(PageNumberPagination):
    page_size             = 20
    page_size_query_param = 'page_size'
    max_page_size         = 100


# =============================================================================
# UC-CAT-01 — Listado del catálogo
# =============================================================================

class CatalogueListView(ListAPIView):
    """GET /api/v1/catalogue/ — UC-CAT-01."""
    permission_classes = [AllowAny]
    serializer_class   = ProductListSerializer
    pagination_class   = CataloguePagination
    filter_backends    = [OrderingFilter]
    ordering_fields    = ['price', 'name', 'created_at']
    ordering           = ['-created_at']

    def get_queryset(self):
        qs = Product.objects.filter(
            is_active=True, is_published=True
        ).select_related('category')

        category_slug = self.request.query_params.get('category')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        return qs

    @extend_schema(
        summary='Ver catálogo de productos',
        description='Listado paginado de productos activos y publicados. '
                    'Accesible sin autenticación (FR-CAT-01.01).',
        parameters=[
            OpenApiParameter('category', str, description='Slug de categoría'),
            OpenApiParameter('ordering', str,
                             description='price / -price / name / -created_at'),
        ],
        responses={200: ProductListSerializer(many=True)},
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# =============================================================================
# UC-CAT-02 — Detalle de producto
# =============================================================================

class ProductDetailView(RetrieveAPIView):
    """GET /api/v1/catalogue/<slug>/ — UC-CAT-02."""
    permission_classes = [AllowAny]
    serializer_class   = ProductDetailSerializer
    lookup_field       = 'slug'

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True, is_published=True
        ).select_related('category')

    @extend_schema(
        summary='Ver detalle de producto',
        description='Ficha completa de un producto activo y publicado. '
                    'Accesible sin autenticación. '
                    'Retorna 404 si el producto no existe o no está publicado.',
        responses={
            200: ProductDetailSerializer,
            404: None,
        },
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# =============================================================================
# UC-CAT-03 + UC-SRCH-01 + UC-CAT-03-EXT — Búsqueda FULLTEXT + filtros
# =============================================================================

class ProductSearchView(ListAPIView):
    """
    GET /api/v1/catalogue/search/?q=<termino> — UC-CAT-03 / UC-SRCH-01

    Búsqueda FULLTEXT MySQL sobre name, description, short_description.
    Parámetros opcionales (UC-CAT-03-EXT):
      category  — ID de categoría
      price_min — precio mínimo (sin IVA)
      price_max — precio máximo (sin IVA)
      in_stock  — 'true' para solo productos con stock
    """
    permission_classes = [AllowAny]
    serializer_class   = ProductSearchSerializer
    pagination_class   = CataloguePagination

    MIN_QUERY_LENGTH = 2

    def get_queryset(self):
        return Product.objects.none()  # se sobreescribe en list()

    def _validate_query(self, q):
        if not q or not q.strip():
            raise ValidationError(
                {'q': 'El término de búsqueda es requerido.',
                 'codigo_error': 'TERMINO_REQUERIDO'},
                code='TERMINO_REQUERIDO',
            )
        q = q.strip()
        if len(q) < self.MIN_QUERY_LENGTH:
            raise ValidationError(
                {'q': f'El término debe tener al menos {self.MIN_QUERY_LENGTH} caracteres.',
                 'codigo_error': 'TERMINO_DEMASIADO_CORTO'},
                code='TERMINO_DEMASIADO_CORTO',
            )
        return q

    def list(self, request, *args, **kwargs):
        q = self._validate_query(request.query_params.get('q', ''))

        qs = Product.objects.filter(
            is_active=True, is_published=True
        ).select_related('category')

        # UC-SRCH-01 — FULLTEXT MySQL
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(short_description__icontains=q)
        )

        # UC-CAT-03-EXT — filtros avanzados
        category_id = request.query_params.get('category')
        if category_id:
            qs = qs.filter(category_id=category_id)

        price_min = request.query_params.get('price_min')
        if price_min:
            try:
                qs = qs.filter(price__gte=Decimal(price_min))
            except InvalidOperation:
                raise ValidationError({'price_min': 'Valor numérico inválido.'})

        price_max = request.query_params.get('price_max')
        if price_max:
            try:
                qs = qs.filter(price__lte=Decimal(price_max))
            except InvalidOperation:
                raise ValidationError({'price_max': 'Valor numérico inválido.'})

        if request.query_params.get('in_stock', '').lower() == 'true':
            qs = qs.filter(stock__gt=0)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        summary='Buscar productos',
        description='Búsqueda de productos por texto libre (nombre, descripción). '
                    'Mínimo 2 caracteres. Accesible sin autenticación.\n\n'
                    'Filtros opcionales (UC-CAT-03-EXT): category, price_min, '
                    'price_max, in_stock.',
        parameters=[
            OpenApiParameter('q', str, required=True,
                             description='Término de búsqueda (mín. 2 caracteres)'),
            OpenApiParameter('category', OpenApiTypes.INT,
                             description='ID de categoría'),
            OpenApiParameter('price_min', OpenApiTypes.DECIMAL,
                             description='Precio mínimo'),
            OpenApiParameter('price_max', OpenApiTypes.DECIMAL,
                             description='Precio máximo'),
            OpenApiParameter('in_stock', OpenApiTypes.BOOL,
                             description='Solo productos con stock'),
        ],
        responses={
            200: ProductSearchSerializer(many=True),
            400: None,
        },
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
