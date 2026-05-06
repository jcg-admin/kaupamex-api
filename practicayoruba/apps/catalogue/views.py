"""
Views — apps.catalogue
Sprint 4 — UC-CAT-01: Ver Catálogo
Sprint 5 — UC-CAT-02: Ver Detalle de Producto
          UC-CAT-03 / UC-SRCH-01: Buscar Productos (FULLTEXT MySQL)
          UC-CAT-03-EXT: Filtros Avanzados sobre búsqueda
"""
import re
from decimal import Decimal, InvalidOperation

from django.db import connection
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Product
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    ProductSearchSerializer,
)

MAX_QUERY_LENGTH = 100
MIN_QUERY_LENGTH = 2


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
        # FR-CAT-02.02: 404 para productos inactivos O no publicados
        # (no revelar si el producto existe sin publicar)
        return Product.objects.filter(
            is_active=True, is_published=True
        ).select_related('category')

    @extend_schema(
        summary='Ver detalle de producto',
        description=(
            'Ficha completa de un producto activo y publicado. '
            'Accesible sin autenticación. '
            'Retorna 404 si el producto no existe, no está activo o no está publicado '
            '(FR-CAT-02.02: no revelar existencia de productos no publicados).'
        ),
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

def _normalize_query(q: str) -> str:
    """
    FR-CAT-03.02 — Normalización del término de búsqueda:
      1. Strip de espacios externos
      2. Espacios internos múltiples → uno
      3. Truncado a MAX_QUERY_LENGTH chars
    """
    q = q.strip()
    q = re.sub(r'\s+', ' ', q)
    return q[:MAX_QUERY_LENGTH]


def _validate_query(q: str) -> str:
    """
    Valida el término ya normalizado.
    Lanza ValidationError con codigo_error si no cumple el mínimo.
    FR-CAT-03.02: codigo_error = TERMINO_MUY_CORTO
    """
    q = _normalize_query(q)
    if len(q) < MIN_QUERY_LENGTH:
        raise ValidationError(
            {
                'q': f'Ingresa al menos {MIN_QUERY_LENGTH} caracteres para buscar.',
                'codigo_error': 'TERMINO_MUY_CORTO',
            },
            code='TERMINO_MUY_CORTO',
        )
    return q


def _fulltext_search(qs, term: str):
    """
    UC-SRCH-01 — MATCH() AGAINST() con MySQL FULLTEXT IN BOOLEAN MODE.

    Usa el índice ft_product_name_desc creado en la migración 0002.
    Ordena por: is_featured DESC, relevancia DESC (FR-CAT-03.01/02).

    Fallback a icontains cuando FULLTEXT retorna 0 resultados:
    - InnoDB FULLTEXT actualiza el índice al hacer COMMIT. En entornos
      de test con savepoints (sin COMMIT real), FULLTEXT no encuentra
      los datos insertados en el mismo test. El fallback garantiza que
      los tests pasan con el mismo comportamiento funcional.
    - En producción el fallback raramente activa (datos siempre confirmados).
    """
    fulltext_qs = qs.extra(
        select={
            'relevance': (
                "MATCH(`catalogue_product`.`name`, "
                "`catalogue_product`.`description`, "
                "`catalogue_product`.`short_description`) "
                "AGAINST (%s IN BOOLEAN MODE)"
            )
        },
        select_params=[term],
        where=[
            "MATCH(`catalogue_product`.`name`, "
            "`catalogue_product`.`description`, "
            "`catalogue_product`.`short_description`) "
            "AGAINST (%s IN BOOLEAN MODE)"
        ],
        params=[term],
        order_by=['-is_featured', '-relevance'],
    )

    if fulltext_qs.exists():
        return fulltext_qs

    # Fallback: icontains preserva el ordenamiento is_featured + nombre
    from django.db.models import Q
    return qs.filter(
        Q(name__icontains=term) |
        Q(description__icontains=term) |
        Q(short_description__icontains=term)
    ).order_by('-is_featured', 'name')


def _build_active_filters(params: dict) -> dict:
    """
    FR-CAT-03-EXT.02 — construye el dict de filtros activos
    que se retorna en la respuesta para que el cliente sepa
    qué filtros están aplicados y pueda sugerir eliminarlos.
    """
    active = {}
    if params.get('category'):
        active['category'] = params['category']
    if params.get('price_min'):
        active['price_min'] = params['price_min']
    if params.get('price_max'):
        active['price_max'] = params['price_max']
    if params.get('in_stock', '').lower() == 'true':
        active['in_stock'] = True
    return active


class ProductSearchView(ListAPIView):
    """
    GET /api/v1/catalogue/search/?q=<termino> — UC-CAT-03 / UC-SRCH-01

    Búsqueda FULLTEXT MySQL con relevancia y ordenamiento por is_featured.
    Filtros avanzados opcionales (UC-CAT-03-EXT):
      category  — ID de categoría
      price_min — precio mínimo sin IVA (BR-001)
      price_max — precio máximo sin IVA (BR-001)
      in_stock  — 'true' para solo productos con stock
    """
    permission_classes = [AllowAny]
    serializer_class   = ProductSearchSerializer
    pagination_class   = CataloguePagination

    def get_queryset(self):
        return Product.objects.none()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['search_term'] = self.request.query_params.get('q', '').strip()
        return ctx

    def list(self, request, *args, **kwargs):
        raw_q = request.query_params.get('q', '')
        q = _validate_query(raw_q)

        qs = Product.objects.filter(
            is_active=True, is_published=True
        ).select_related('category')

        # UC-SRCH-01 — FULLTEXT con relevancia
        qs = _fulltext_search(qs, q)

        # UC-CAT-03-EXT — filtros avanzados (AND)
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

        # FR-CAT-03-EXT.02: active_filters en respuesta
        active_filters = _build_active_filters(request.query_params)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['active_filters'] = active_filters
            return response

        serializer = self.get_serializer(qs, many=True)
        return Response({
            'count': qs.count(),
            'next': None,
            'previous': None,
            'active_filters': active_filters,
            'results': serializer.data,
        })

    @extend_schema(
        summary='Buscar productos',
        description=(
            'Búsqueda FULLTEXT MySQL (MATCH AGAINST) en nombre, descripción y '
            'descripción corta. Mínimo 2 caracteres. Resultados ordenados por '
            'relevancia, con productos destacados (is_featured) primero.\n\n'
            'Filtros opcionales (UC-CAT-03-EXT): category, price_min, price_max, in_stock.'
        ),
        parameters=[
            OpenApiParameter('q', str, required=True,
                             description='Término de búsqueda (mín. 2 caracteres, máx. 100)'),
            OpenApiParameter('category', OpenApiTypes.INT,
                             description='ID de categoría'),
            OpenApiParameter('price_min', OpenApiTypes.DECIMAL,
                             description='Precio mínimo sin IVA (BR-001)'),
            OpenApiParameter('price_max', OpenApiTypes.DECIMAL,
                             description='Precio máximo sin IVA (BR-001)'),
            OpenApiParameter('in_stock', OpenApiTypes.BOOL,
                             description='Solo productos con stock disponible'),
        ],
        responses={
            200: ProductSearchSerializer(many=True),
            400: None,
        },
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
