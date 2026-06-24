"""
Views V2 — apps.catalogue

F1: Unified products endpoint replacing three v1 endpoints:
  - GET /api/v1/catalogue/          (browse/list)
  - GET /api/v1/catalogue/search/   (fulltext search)
  - GET /api/v1/catalogue/autocomplete/ (prefix suggestions)

Single unified endpoint: GET /api/v2/products/
  No ?q=                  → catalogue list (inherits CatalogueListView)
  ?q=<term>               → fulltext search (replaces /catalogue/search/)
  ?q=<term>&autocomplete=1 → prefix suggestions (replaces /catalogue/autocomplete/)
"""
from decimal import Decimal, InvalidOperation
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .models import Product
from .serializers import AutocompleteSerializer, ProductSearchSerializer
from .views import (
    CatalogueListView,
    MIN_QUERY_LENGTH,
    AUTOCOMPLETE_MAX_RESULTS,
    AUTOCOMPLETE_CACHE_TTL,
    _normalize_query,
    _validate_query,
    _fulltext_search,
    _build_active_filters,
    _record_history_async,
)


class ProductListV2View(CatalogueListView):
    """
    GET /api/v2/products/

    Unified endpoint: list, search, or autocomplete depending on ?q=.
    No ?q=   → delegates to CatalogueListView (filters, pagination, ordering).
    ?q=term  → fulltext search with ProductSearchSerializer.
    ?q=term&autocomplete=1 → prefix suggestions (cached).
    """

    @extend_schema(
        summary='List, search, or autocomplete products (v2)',
        parameters=[
            OpenApiParameter('q', str, description=(
                'Search term. Omit for catalogue list. '
                'Add &autocomplete=1 for prefix suggestions.'
            )),
            OpenApiParameter('autocomplete', OpenApiTypes.BOOL, description='Return autocomplete suggestions for ?q=.'),
            OpenApiParameter('category', str, description='Category slug (list mode) or integer ID (search mode).'),
            OpenApiParameter('price_min', OpenApiTypes.DECIMAL),
            OpenApiParameter('price_max', OpenApiTypes.DECIMAL),
            OpenApiParameter('ordering', str),
            OpenApiParameter('in_stock', OpenApiTypes.BOOL),
        ],
        responses={200: None},
        tags=['products-v2'],
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        search_term = getattr(self, '_search_term', None)
        if search_term:
            ctx['search_term'] = search_term
        return ctx

    def list(self, request, *args, **kwargs):
        q = request.query_params.get('q', '').strip()
        if not q:
            return super().list(request, *args, **kwargs)
        if request.query_params.get('autocomplete', '').lower() in ('1', 'true'):
            return self._autocomplete_response(q)
        return self._search_response(request, q)

    def _autocomplete_response(self, prefijo):
        prefijo = _normalize_query(prefijo)
        if len(prefijo) < MIN_QUERY_LENGTH:
            return Response([])
        cache_key = f'autocomplete:{prefijo.lower().replace(" ", "_")}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        qs = (
            Product.objects
            .filter(name__istartswith=prefijo, is_active=True, is_published=True)
            .only('id', 'name', 'slug')
            .order_by('name')[:AUTOCOMPLETE_MAX_RESULTS]
        )
        data = AutocompleteSerializer(qs, many=True).data
        cache.set(cache_key, data, AUTOCOMPLETE_CACHE_TTL)
        return Response(data)

    def _search_response(self, request, q):
        q = _validate_query(q)
        self._search_term = q
        qs = (
            Product.objects
            .filter(is_active=True, is_published=True)
            .prefetch_related('categories', 'images', 'discounts', 'variants')
        )
        qs = _fulltext_search(qs, q)
        category = request.query_params.get('category')
        if category:
            try:
                cat_pk = int(category)
            except (ValueError, TypeError):
                raise ValidationError({'category': 'El ID de categoría debe ser un entero.'})
            qs = qs.filter(categories__id=cat_pk).distinct()
        price_min = request.query_params.get('price_min')
        if price_min:
            try:
                val = Decimal(price_min)
                if val < 0:
                    raise ValidationError({'price_min': 'El precio mínimo no puede ser negativo.'})
                qs = qs.filter(price__gte=val)
            except InvalidOperation:
                raise ValidationError({'price_min': 'Valor numérico inválido.'})
        price_max = request.query_params.get('price_max')
        if price_max:
            try:
                val = Decimal(price_max)
                if val < 0:
                    raise ValidationError({'price_max': 'El precio máximo no puede ser negativo.'})
                qs = qs.filter(price__lte=val)
            except InvalidOperation:
                raise ValidationError({'price_max': 'Valor numérico inválido.'})
        if request.query_params.get('in_stock', '').lower() == 'true':
            qs = qs.filter(stock__gt=0)
        if request.user and request.user.is_authenticated:
            _record_history_async(request.user, q)
        active_filters = _build_active_filters(request.query_params)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ProductSearchSerializer(page, many=True, context=self.get_serializer_context())
            response = self.get_paginated_response(serializer.data)
            response.data['active_filters'] = active_filters
            return response
        serializer = ProductSearchSerializer(qs, many=True, context=self.get_serializer_context())
        return Response({
            'count': qs.count(),
            'next': None,
            'previous': None,
            'active_filters': active_filters,
            'results': serializer.data,
        })
