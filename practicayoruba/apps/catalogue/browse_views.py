"""
Catalogue browse extensions (P-17 closure).

Exposes new public endpoints at top-level URLs while reusing existing
queries / serializers. The Product model is NOT modified (per the
P-17 ground rules).

  GET /api/v1/products/<slug>/related/
  GET /api/v1/categories/
  GET /api/v1/catalogue/search/      (with normalized_query in payload)

Search history persistence is delegated to apps.search_history.
"""
import re
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Product
from .serializers import (
    CategoryWithCountSerializer,
    ProductListSerializer,
    ProductSearchSerializer,
)
from .views import (
    CATEGORY_TREE_CACHE_KEY,
    CATEGORY_TREE_CACHE_TTL,
    _build_active_filters,
    _build_category_tree_with_counts,
    _fulltext_search,
    _get_category_descendants,
    _normalize_query,
    _record_history_async,
    _validate_query,
    CataloguePagination,
)
from apps.search_history.models import SearchEntry


# =============================================================================
# GET /api/v1/products/<slug>/related/ — UC-CAT-07
# =============================================================================

class RelatedProductsView(APIView):
    """
    Related products: same category, exclude self, ordered by featured
    + creation. Limit 8. Empty list if product not found is NOT
    acceptable — return 404 with loud error code (DEC-DOC-008).
    """
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer

    @extend_schema(
        summary='Related products by category (UC-CAT-07).',
        tags=['catalogue'],
    )
    def get(self, request, slug):
        try:
            product = Product.objects.get(
                slug=slug, is_active=True, is_published=True,
            )
        except Product.DoesNotExist:
            raise NotFound({
                'detail': 'Producto no encontrado.',
                'codigo_error': 'PRODUCTO_NO_ENCONTRADO',
            })

        related = (
            Product.objects.filter(
                category=product.category,
                is_active=True, is_published=True,
            )
            .exclude(pk=product.pk)
            .select_related('category')
            .order_by('-is_featured', '-created_at')[:8]
        )
        data = ProductListSerializer(related, many=True).data
        return Response({
            'product_id': product.id,
            'category_id': product.category_id,
            'results': data,
        })


# =============================================================================
# GET /api/v1/categories/ — UC-CAT-08 (alias for /api/v1/catalogue/categories/).
# =============================================================================

class CategoryTreeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Public category tree (UC-CAT-08).',
        responses={200: CategoryWithCountSerializer(many=True)},
        tags=['catalogue'],
    )
    def get(self, request):
        cached = cache.get(CATEGORY_TREE_CACHE_KEY)
        if cached is not None:
            return Response(cached)
        roots = _build_category_tree_with_counts()
        data = CategoryWithCountSerializer(roots, many=True).data
        cache.set(CATEGORY_TREE_CACHE_KEY, data, CATEGORY_TREE_CACHE_TTL)
        return Response(data)


# =============================================================================
# GET /api/v1/catalogue/search/ wrapper — adds normalized_query + persists
# to apps.search_history.SearchEntry. Coexists with the existing search view.
# =============================================================================

class CatalogueSearchView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ProductSearchSerializer

    @extend_schema(
        summary='Search products with normalized_query (UC-CAT-03).',
        parameters=[
            OpenApiParameter('q', str, required=True),
            OpenApiParameter('category', str, required=False),
            OpenApiParameter('price_min', float, required=False),
            OpenApiParameter('price_max', float, required=False),
            OpenApiParameter('page', int, required=False),
        ],
        tags=['catalogue'],
    )
    def get(self, request):
        raw_q = request.query_params.get('q', '')
        q = _validate_query(raw_q)

        qs = Product.objects.filter(
            is_active=True, is_published=True,
        ).select_related('category')
        qs = _fulltext_search(qs, q)

        category_slug = request.query_params.get('category')
        if category_slug:
            try:
                cat_id = int(category_slug)
                qs = qs.filter(category_id=cat_id)
            except (TypeError, ValueError):
                pks = _get_category_descendants(category_slug)
                if not pks:
                    qs = qs.none()
                else:
                    qs = qs.filter(category_id__in=pks)

        for key in ('price_min', 'price_max'):
            raw = request.query_params.get(key)
            if not raw:
                continue
            try:
                val = Decimal(raw)
            except InvalidOperation:
                raise ValidationError({
                    key: 'Valor numerico invalido.',
                    'codigo_error': 'PRICE_FILTER_INVALIDO',
                })
            if key == 'price_min':
                qs = qs.filter(price__gte=val)
            else:
                qs = qs.filter(price__lte=val)

        if request.query_params.get('in_stock', '').lower() == 'true':
            qs = qs.filter(stock__gt=0)

        normalized = _normalize_query(q)

        # Legacy history (catalogue.SearchHistory) — keep old contract green.
        if request.user and request.user.is_authenticated:
            _record_history_async(request.user, q)
            SearchEntry.objects.create(
                user=request.user,
                query=raw_q[:200],
                normalized_query=normalized,
                results_count=qs.count(),
            )

        paginator = CataloguePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        ctx = {'search_term': q}
        serializer_cls = ProductSearchSerializer
        if page is not None:
            results = serializer_cls(page, many=True, context=ctx).data
            paginated = paginator.get_paginated_response(results).data
            paginated['normalized_query'] = normalized
            paginated['active_filters'] = _build_active_filters(request.query_params)
            return Response(paginated)

        results = serializer_cls(qs, many=True, context=ctx).data
        return Response({
            'count': qs.count(),
            'next': None, 'previous': None,
            'normalized_query': normalized,
            'active_filters': _build_active_filters(request.query_params),
            'results': results,
        })
