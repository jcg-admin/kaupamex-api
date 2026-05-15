"""
Views — apps.catalogue

Sprint 4 — UC-CAT-01
Sprint 5 — UC-CAT-02, UC-CAT-03, UC-CAT-03-EXT, UC-SRCH-01
Sprint 6 — UC-SRCH-02, UC-SRCH-03, UC-CAT-04, UC-CAT-05, UC-CAT-06
"""
import re
import threading
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.db import connection
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Category, Product, SearchHistory
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    ProductSearchSerializer,
    AutocompleteSerializer,
    SearchHistorySerializer,
    CategoryAdminSerializer,
    CategoryWithCountSerializer,
    ProductAdminSerializer,
)

MAX_QUERY_LENGTH = 100
MIN_QUERY_LENGTH = 2
AUTOCOMPLETE_CACHE_TTL   = 60    # segundos — UC-SRCH-02
AUTOCOMPLETE_MAX_RESULTS = 5     # UC-SRCH-02
CATEGORY_TREE_CACHE_KEY  = 'categories:tree'
CATEGORY_TREE_CACHE_TTL  = 3600   # 1 hora — UC-CAT-08 (FR-CAT-08.02)
CATEGORY_TREE_CACHE_TTL  = 300   # segundos — UC-CAT-08 (Sprint 7)


# =============================================================================
# Helpers internos
# =============================================================================

def _normalize_query(q: str) -> str:
    q = q.strip()
    q = re.sub(r'\s+', ' ', q)
    return q[:MAX_QUERY_LENGTH]


def _validate_query(q: str) -> str:
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
    Fallback a icontains para entornos de test sin COMMIT (savepoints).
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
    from django.db.models import Q
    return qs.filter(
        Q(name__icontains=term) |
        Q(description__icontains=term) |
        Q(short_description__icontains=term)
    ).order_by('-is_featured', 'name')


def _get_category_descendants(slug: str) -> set:
    """
    Retorna el set de PKs de la categoría con ese slug y todos sus
    descendientes activos. UC-CAT-04 (FR-CAT-04.02).
    Retorna set vacío si el slug no existe o la categoría está inactiva.
    """
    try:
        root = Category.objects.get(slug=slug, is_active=True)
    except Category.DoesNotExist:
        return set()
    return root.get_descendants_pks()


def _build_active_filters(params: dict) -> dict:
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


def _record_history_async(user, term: str) -> None:
    """
    Guarda el término en SearchHistory en un hilo separado.
    No bloquea la respuesta al visitante. UC-SRCH-03.

    Estrategia: threading (sin Celery hasta Sprint 27).
    Si el hilo falla, el error se registra en log pero no se propaga.
    El historial no es dato crítico — una entrada perdida es aceptable.
    """
    def _save():
        try:
            SearchHistory.record(user=user, term=term)
        except Exception as exc:
            import logging
            logging.getLogger('apps').warning(
                'SearchHistory.record falló para user=%s term=%r: %s',
                user.pk, term, exc,
            )

    t = threading.Thread(target=_save, daemon=True)
    t.start()


# =============================================================================
# Paginación
# =============================================================================

class CataloguePagination(PageNumberPagination):
    page_size             = 20
    page_size_query_param = 'page_size'
    max_page_size         = 100


# =============================================================================
# UC-CAT-01 — Listado del catálogo
# UC-CAT-04 — Filtrar por categoría con subcategorías
# UC-CAT-05 — Filtrar por rango de precio
# =============================================================================

class CatalogueListView(ListAPIView):
    """
    GET /api/v1/catalogue/

    UC-CAT-01: listado paginado.
    UC-CAT-04: filtro ?category=<slug> incluye la categoría y sus descendientes.
    UC-CAT-05: filtros ?price_min= y ?price_max= operan sobre precio base (BR-001).
    """
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

        # UC-CAT-04 — filtro por categoría + descendientes
        category_slug = self.request.query_params.get('category')
        if category_slug:
            pks = _get_category_descendants(category_slug)
            if not pks:
                return Product.objects.none()
            qs = qs.filter(category_id__in=pks)

        # UC-CAT-05 — filtro por rango de precio base (BR-001)
        price_min = self.request.query_params.get('price_min')
        if price_min:
            try:
                qs = qs.filter(price__gte=Decimal(price_min))
            except InvalidOperation:
                raise ValidationError({'price_min': 'Valor numérico inválido.'})

        price_max = self.request.query_params.get('price_max')
        if price_max:
            try:
                qs = qs.filter(price__lte=Decimal(price_max))
            except InvalidOperation:
                raise ValidationError({'price_max': 'Valor numérico inválido.'})

        return qs

    @extend_schema(
        summary='Ver catálogo de productos',
        description=(
            'Listado paginado de productos activos y publicados. '
            'Filtros: category (slug, incluye subcategorías), '
            'price_min, price_max (precio base sin IVA, BR-001).'
        ),
        parameters=[
            OpenApiParameter('category', str, description='Slug de categoría (incluye subcategorías)'),
            OpenApiParameter('price_min', OpenApiTypes.DECIMAL, description='Precio mínimo base sin IVA'),
            OpenApiParameter('price_max', OpenApiTypes.DECIMAL, description='Precio máximo base sin IVA'),
            OpenApiParameter('ordering', str, description='price / -price / name / -created_at'),
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
        responses={200: ProductDetailSerializer, 404: None},
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# =============================================================================
# UC-CAT-03 + UC-SRCH-01 + UC-CAT-03-EXT — Búsqueda
# =============================================================================

class ProductSearchView(ListAPIView):
    """GET /api/v1/catalogue/search/?q= — UC-CAT-03 / UC-SRCH-01."""
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

        qs = _fulltext_search(qs, q)

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

        # UC-SRCH-03 — guardar historial si el usuario está autenticado
        if request.user and request.user.is_authenticated:
            _record_history_async(request.user, q)

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
            'next': None, 'previous': None,
            'active_filters': active_filters,
            'results': serializer.data,
        })

    @extend_schema(
        summary='Buscar productos',
        parameters=[
            OpenApiParameter('q', str, required=True),
            OpenApiParameter('category', OpenApiTypes.INT),
            OpenApiParameter('price_min', OpenApiTypes.DECIMAL),
            OpenApiParameter('price_max', OpenApiTypes.DECIMAL),
            OpenApiParameter('in_stock', OpenApiTypes.BOOL),
        ],
        responses={200: ProductSearchSerializer(many=True), 400: None},
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


# =============================================================================
# UC-SRCH-02 — Autocomplete
# =============================================================================

class AutocompleteView(APIView):
    """
    GET /api/v1/catalogue/autocomplete/?q=<prefijo>

    Retorna hasta 5 sugerencias de productos por prefijo en Product.name.
    Cache DatabaseCache con clave autocomplete:<prefijo> TTL 60s.
    Mínimo 2 caracteres. Respuesta vacía si prefijo inválido (sin error visible).
    UC-SRCH-02.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Autocomplete de productos',
        description='Sugerencias por prefijo en nombre del producto. Mín. 2 chars. Máx. 5 resultados.',
        parameters=[
            OpenApiParameter('q', str, required=True, description='Prefijo (mín. 2 caracteres)'),
        ],
        responses={200: AutocompleteSerializer(many=True)},
        tags=['catalogue'],
    )
    def get(self, request):
        raw_q = request.query_params.get('q', '').strip()
        prefijo = _normalize_query(raw_q)

        # Mínimo de caracteres — retorna vacío silenciosamente (sin error 400)
        if len(prefijo) < MIN_QUERY_LENGTH:
            return Response([])

        cache_key = f'autocomplete:{prefijo.lower()}'
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


# =============================================================================
# UC-SRCH-03 — Historial de búsquedas
# =============================================================================

class SearchHistoryView(APIView):
    """
    GET    /api/v1/catalogue/search/history/    — ver historial (últimas 20 búsquedas)
    DELETE /api/v1/catalogue/search/history/    — borrar todo el historial
    DELETE /api/v1/catalogue/search/history/<id>/ — borrar una entrada
    UC-SRCH-03.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Ver historial de búsquedas',
        description='Últimas 20 búsquedas del comprador autenticado, ordenadas por más reciente.',
        responses={200: SearchHistorySerializer(many=True)},
        tags=['catalogue'],
    )
    def get(self, request):
        qs = SearchHistory.objects.filter(user=request.user)
        serializer = SearchHistorySerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Borrar todo el historial de búsquedas',
        responses={204: None},
        tags=['catalogue'],
    )
    def delete(self, request):
        SearchHistory.objects.filter(user=request.user).delete()
        return Response(status=204)


class SearchHistoryDetailView(APIView):
    """
    DELETE /api/v1/catalogue/search/history/<pk>/ — eliminar una entrada.
    UC-SRCH-03 (Alternativa A).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Borrar una entrada del historial',
        responses={204: None, 404: None},
        tags=['catalogue'],
    )
    def delete(self, request, pk):
        try:
            entry = SearchHistory.objects.get(pk=pk, user=request.user)
        except SearchHistory.DoesNotExist:
            raise NotFound('Entrada no encontrada.')
        entry.delete()
        return Response(status=204)


# =============================================================================
# UC-CAT-06 — Gestionar Categorías (Admin CRUD)
# =============================================================================

class CategoryAdminViewSet(ModelViewSet):
    """
    GET    /api/v1/admin/categories/       — listar categorías
    POST   /api/v1/admin/categories/       — crear categoría
    GET    /api/v1/admin/categories/<pk>/  — detalle
    PATCH  /api/v1/admin/categories/<pk>/  — editar
    DELETE /api/v1/admin/categories/<pk>/  — desactivar (soft delete)

    UC-CAT-06. Solo administradores (is_staff=True).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = CategoryAdminSerializer
    queryset           = Category.objects.all().order_by('name')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_destroy(self, instance):
        """
        Soft delete: desactiva la categoría en lugar de eliminarla.
        No se puede eliminar una categoría con productos activos (FR-CAT-06.02).
        """
        if instance.products.filter(is_active=True).exists():
            raise ValidationError({
                'detail': (
                    'No se puede desactivar una categoria con productos activos. '
                    'Reasigna o desactiva los productos primero.'
                ),
                'codigo_error': 'CATEGORIA_CON_PRODUCTOS',
            })
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        self._invalidate_category_cache()

    def perform_create(self, serializer):
        instance = serializer.save()
        self._invalidate_category_cache()
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        self._invalidate_category_cache()
        return instance

    def _invalidate_category_cache(self):
        """FR-CAT-06.02: invalidar cache del árbol de categorías tras cualquier mutación."""
        cache.delete(CATEGORY_TREE_CACHE_KEY)

    @extend_schema(
        summary='Listar categorías (admin)',
        tags=['admin-catalogue'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Crear categoría',
        tags=['admin-catalogue'],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary='Editar categoría',
        tags=['admin-catalogue'],
    )
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Desactivar categoría (soft delete)',
        responses={204: None, 400: None},
        tags=['admin-catalogue'],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


# =============================================================================
# Sprint 7 — UC-CAT-07, UC-CAT-08, UC-CAT-09, UC-CAT-10
# =============================================================================

# =============================================================================
# UC-CAT-08 — Árbol de categorías público
# =============================================================================

def _build_category_tree_with_counts():
    """
    Construye el árbol de categorías con product_count acumulado.
    H-S7-008: 2 queries totales — O(1) independiente del nro de categorías.

    Query 1: todos los productos activos y publicados agrupados por category_id
    Query 2: todas las categorías activas con sus hijos (prefetch_related)
    Luego se propaga bottom-up en Python.
    """
    from django.db.models import Count

    # Query 1: conteo directo por category_id
    direct_counts = dict(
        Product.objects.filter(is_active=True, is_published=True)
        .values('category_id')
        .annotate(n=Count('id'))
        .values_list('category_id', 'n')
    )

    # Query 2: todas las categorías con hijos pre-cargados
    all_cats = list(
        Category.objects.filter(is_active=True)
        .prefetch_related('children')
        .order_by('name')
    )

    # Índice rápido por pk
    cat_map = {c.pk: c for c in all_cats}

    # Inicializar conteos
    accumulated = {c.pk: direct_counts.get(c.pk, 0) for c in all_cats}

    # Propagación bottom-up: sumar hijos al padre
    # Orden inverso al de profundidad para garantizar que hijos estén
    # calculados antes que sus padres
    def _accumulate(cat_pk: int) -> int:
        total = accumulated[cat_pk]
        cat = cat_map[cat_pk]
        for child in cat.children.all():
            if child.pk in accumulated:
                total += _accumulate(child.pk)
        accumulated[cat_pk] = total
        return total

    # Solo propagar desde raíces (sin parent)
    roots = [c for c in all_cats if c.parent_id is None]
    for root in roots:
        _accumulate(root.pk)

    # Anotar en el objeto para que el serializer lo lea
    for cat in all_cats:
        cat.product_count = accumulated[cat.pk]

    return roots


class CategoryListView(APIView):
    """
    GET /api/v1/catalogue/categories/

    Árbol completo de categorías activas con product_count acumulado.
    Cache DatabaseCache 'categories:tree' TTL 3600s (1 hora).
    La invalidación ocurre en CategoryAdminViewSet tras cualquier mutación.
    UC-CAT-08 (FR-CAT-08.01, FR-CAT-08.02).
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Árbol de categorías del catálogo',
        description=(
            'Estructura jerárquica completa de categorías activas con conteo '
            'de productos activos y publicados (acumulado en descendientes). '
            'Respuesta cacheada 1 hora.'
        ),
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
# UC-CAT-09 y UC-CAT-10 — CRUD admin de productos
# =============================================================================

class ProductAdminViewSet(ModelViewSet):
    """
    GET    /api/v1/admin/products/       — listar todos los productos
    POST   /api/v1/admin/products/       — crear producto (UC-CAT-09)
    GET    /api/v1/admin/products/<pk>/  — detalle admin
    PATCH  /api/v1/admin/products/<pk>/  — editar producto (UC-CAT-10)
    DELETE /api/v1/admin/products/<pk>/  — desactivar producto (soft delete)

    Solo administradores (is_staff=True).
    Imágenes: diferidas a Sprint 8. images=[] en la respuesta.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = ProductAdminSerializer
    queryset           = (
        Product.objects
        .select_related('category')
        .order_by('-created_at')
    )
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_create(self, serializer):
        serializer.save()
        # No invalidamos categories:tree al crear un producto —
        # el product_count de la categoría sube, pero solo importa
        # cuando el producto quede publicado. Se invalida en perform_update.

    def perform_update(self, serializer):
        old_category_pk = self.get_object().category_id
        instance = serializer.save()
        # H-S7-007: invalidar categories:tree si cambió la categoría
        if instance.category_id != old_category_pk:
            cache.delete(CATEGORY_TREE_CACHE_KEY)

    def perform_destroy(self, instance):
        """Soft delete: is_active=False."""
        instance.is_active = False
        instance.is_published = False
        instance.save(update_fields=['is_active', 'is_published'])
        cache.delete(CATEGORY_TREE_CACHE_KEY)

    @extend_schema(summary='Listar productos (admin)', tags=['admin-catalogue'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Crear producto',
        description=(
            'Crea el producto con is_published=False por defecto. '
            'Imágenes diferidas a Sprint 8.'
        ),
        tags=['admin-catalogue'],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary='Editar producto (PATCH)',
        description=(
            'Solo los campos enviados se modifican. '
            'BR-005: los cambios de precio no afectan órdenes ya creadas. '
            'Imágenes diferidas a Sprint 8.'
        ),
        tags=['admin-catalogue'],
    )
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Desactivar producto (soft delete)',
        responses={204: None},
        tags=['admin-catalogue'],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
