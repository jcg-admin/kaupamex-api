import csv
import io
import uuid
from django.http import HttpResponse
from django.db import transaction
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
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
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
    return root.get_descendants_ids()


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
    Guarda el término en SearchHistory de forma síncrona.
    Convertido a síncrono para garantizar FK consistency en tests.
    UC-SRCH-03.
    """
    try:
        SearchHistory.record(user=user, term=term)
    except Exception:
        logger.warning(
            'SearchHistory.record falló para user=%s term=%r: %s',
            getattr(user, 'pk', user), term, exc_info=True,
        )
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

def _count_active_carts(product) -> int:
    """Cuenta CartItems activos que contienen este producto (Sprint 12)."""
    try:
        from apps.cart.models import CartItem
        return CartItem.objects.filter(product=product).count()
    except Exception:
        return 0


def _count_wishlist_items(product) -> int:
    """Cuenta WishlistItems activos que contienen este producto (Sprint 14)."""
    try:
        from apps.wishlist.models import WishlistItem
        return WishlistItem.objects.filter(product=product).count()
    except Exception:
        return 0


# =============================================================================
# Sprint 8 — UC-CAT-11: Desactivar producto con preview de impacto
# =============================================================================

class ProductDeactivateAction:
    """
    Mixin para ProductAdminViewSet.
    POST /api/v1/admin/products/<pk>/deactivate/

    Sin body  → retorna preview de impacto (stock, carts=0, wishlists=0).
    {"confirm": true} → desactiva y purga caches.
    """

    @action(detail=True, methods=['post'], url_path='deactivate')
    @extend_schema(
        summary='Desactivar producto con preview de impacto',
        description=(
            'Sin body: retorna el impacto (stock, carritos, wishlists). '
            'Con {"confirm": true}: desactiva el producto y purga caches. '
            'UC-CAT-11 (FR-CAT-11.02).'
        ),
        responses={
            200: OpenApiResponse(description='Preview de impacto o confirmacion de desactivacion.'),
            400: OpenApiResponse(description='Producto ya desactivado.'),
        },
        tags=['admin-catalogue'],
    )
    def deactivate(self, request, pk=None):
        from apps.catalogue.models import Product
        product = self.get_object()

        if not product.is_active:
            return Response(
                {'detail': 'El producto ya está desactivado.',
                 'codigo_error': 'PRODUCTO_YA_INACTIVO'},
                status=400,
            )

        # Preview de impacto
        impact = {
            'product_id': product.pk,
            'product_name': product.name,
            'stock': product.stock,
            'active_carts': _count_active_carts(product),
            'wishlists': _count_wishlist_items(product),
        }

        confirm = request.data.get('confirm', False)
        if not confirm:
            impact['message'] = (
                'Envía {"confirm": true} para confirmar la desactivación.'
            )
            return Response(impact, status=200)

        # Confirmar desactivacion
        product.is_active    = False
        product.is_published = False
        product.save(update_fields=['is_active', 'is_published'])

        # Purgar caches (H-S8-001: correccion del perform_destroy de Sprint 7)
        cache.delete(f'product:{product.pk}:detail')
        cache.delete(CATEGORY_TREE_CACHE_KEY)

        return Response({
            **impact,
            'is_active': False,
            'message': 'Producto desactivado correctamente.',
        }, status=200)


class ProductAdminViewSet(ProductDeactivateAction, ModelViewSet):
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
        """Soft delete: is_active=False. Purga caches del producto y árbol."""
        instance.is_active    = False
        instance.is_published = False
        instance.save(update_fields=['is_active', 'is_published'])
        # H-S8-001: purgar también la ficha del producto (Sprint 7 solo purgaba categories:tree)
        cache.delete(f'product:{instance.pk}:detail')
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


# =============================================================================
# Sprint 8 — UC-CAT-12: Sincronizacion de precios en lote
# =============================================================================

PRICE_SYNC_CACHE_TTL = 600   # 10 minutos para la sesion de preview


class ProductPriceSyncView(APIView):
    """
    POST   /api/v1/admin/products/price-sync/          — subir CSV o ajuste porcentual
    POST   /api/v1/admin/products/price-sync/confirm/  — confirmar cambios
    GET    /api/v1/admin/products/price-sync/template/ — descargar plantilla CSV

    UC-CAT-12.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _parse_csv(self, file_obj) -> tuple:
        """
        Parsea el CSV y retorna (filas_validas, filas_invalidas).
        Cada fila valida: {'sku': str, 'product': Product, 'old_price': Decimal, 'new_price': Decimal}
        Cada fila invalida: {'sku': str, 'error': str, 'line': int}
        """
        from apps.catalogue.models import Product
        try:
            content = file_obj.read().decode('utf-8-sig')  # utf-8-sig para BOM de Excel
        except UnicodeDecodeError:
            content = file_obj.read().decode('latin-1')

        reader = csv.DictReader(io.StringIO(content))
        required_cols = {'sku', 'price'}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            return [], [{'sku': '', 'error': 'El CSV debe tener columnas "sku" y "price"', 'line': 0}]

        validas, invalidas = [], []
        sku_index = {p.sku.upper(): p for p in
                     Product.objects.filter(is_active=True).only('id', 'sku', 'price', 'name')}

        for i, row in enumerate(reader, start=2):  # línea 1 = headers
            sku = (row.get('sku') or '').strip().upper()
            price_raw = (row.get('price') or '').strip().replace(',', '.')
            if not sku:
                invalidas.append({'sku': sku, 'error': 'SKU vacío', 'line': i})
                continue
            try:
                new_price = Decimal(price_raw)
                if new_price <= Decimal('0'):
                    raise ValueError('precio <= 0')
            except Exception:
                invalidas.append({'sku': sku, 'error': f'Precio inválido: "{price_raw}"', 'line': i})
                continue

            product = sku_index.get(sku)
            if not product:
                invalidas.append({'sku': sku, 'error': 'SKU no encontrado en el catálogo', 'line': i})
                continue

            validas.append({
                'sku': sku,
                'product_id': product.pk,
                'product_name': product.name,
                'old_price': str(product.price),
                'new_price': str(new_price),
                'diff_pct': round(float((new_price - product.price) / product.price * 100), 2),
            })

        return validas, invalidas

    def _apply_percentage(self, pct: float, category_id=None,
                          price_min=None, price_max=None) -> tuple:
        """Calcula ajuste porcentual. Retorna (filas_validas, [])."""
        from apps.catalogue.models import Product
        qs = Product.objects.filter(is_active=True).only('id', 'sku', 'price', 'name')
        if category_id:
            qs = qs.filter(category_id=category_id)
        if price_min:
            qs = qs.filter(price__gte=price_min)
        if price_max:
            qs = qs.filter(price__lte=price_max)

        multiplier = Decimal(str(1 + pct / 100))
        validas = []
        for p in qs:
            new_price = max(Decimal('0.01'), (p.price * multiplier).quantize(Decimal('0.01')))
            validas.append({
                'sku': p.sku,
                'product_id': p.pk,
                'product_name': p.name,
                'old_price': str(p.price),
                'new_price': str(new_price),
                'diff_pct': pct,
            })
        return validas, []

    @extend_schema(
        summary='Preview de sincronización de precios (CSV o porcentaje)',
        tags=['admin-catalogue'],
    )
    def post(self, request):
        """Subir CSV o iniciar ajuste porcentual — retorna preview con session_id."""
        mode = request.data.get('mode', 'csv')

        if mode == 'percentage':
            try:
                pct = float(request.data.get('pct', 0))
            except (TypeError, ValueError):
                return Response({'detail': 'pct debe ser un número.'}, status=400)
            category_id = request.data.get('category_id')
            price_min   = request.data.get('price_min')
            price_max   = request.data.get('price_max')
            validas, invalidas = self._apply_percentage(pct, category_id, price_min, price_max)
        else:
            csv_file = request.FILES.get('file')
            if not csv_file:
                return Response({'detail': 'Se requiere el archivo CSV.'}, status=400)
            validas, invalidas = self._parse_csv(csv_file)

        session_id = str(uuid.uuid4())
        cache.set(f'price_sync:{session_id}', validas, PRICE_SYNC_CACHE_TTL)

        return Response({
            'session_id': session_id,
            'valid_count':   len(validas),
            'invalid_count': len(invalidas),
            'preview':       validas[:50],   # primeras 50 para no sobrecargar la respuesta
            'errors':        invalidas,
            'message': (
                f'{len(validas)} precios listos para actualizar. '
                f'Usa POST /price-sync/confirm/ con el session_id para confirmar.'
            ),
        })


class ProductPriceSyncConfirmView(APIView):
    """POST /api/v1/admin/products/price-sync/confirm/ — UC-CAT-12."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Confirmar sincronización de precios',
        tags=['admin-catalogue'],
    )
    def post(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'detail': 'session_id requerido.'}, status=400)

        validas = cache.get(f'price_sync:{session_id}')
        if validas is None:
            return Response({
                'detail': 'Sesión expirada o no encontrada. Sube el CSV nuevamente.',
                'codigo_error': 'SESSION_EXPIRADA',
            }, status=400)

        from apps.catalogue.models import Product
        import logging
        logger = logging.getLogger('apps')

        product_ids = [row['product_id'] for row in validas]
        products = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}

        updated = []
        with transaction.atomic():
            for row in validas:
                p = products.get(row['product_id'])
                if not p:
                    continue
                p.price = Decimal(row['new_price'])
                updated.append(p)
            Product.objects.bulk_update(updated, ['price'])

        # Purgar caches de fichas modificadas (H-S8-005)
        keys_to_delete = [f'product:{p.pk}:detail' for p in updated]
        if keys_to_delete:
            cache.delete_many(keys_to_delete)

        # Invalidar sesion
        cache.delete(f'price_sync:{session_id}')

        logger.info('price_sync: %d productos actualizados por %s',
                    len(updated), request.user.username)

        return Response({
            'updated_count': len(updated),
            'message': f'{len(updated)} precios actualizados correctamente.',
        })


class ProductPriceSyncTemplateView(APIView):
    """GET /api/v1/admin/products/price-sync/template/ — UC-CAT-12 Alt-C."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Descargar plantilla CSV de precios',
        tags=['admin-catalogue'],
    )
    def get(self, request):
        from apps.catalogue.models import Product
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="price-template.csv"'
        response.write('\ufeff')  # BOM para Excel

        writer = csv.writer(response)
        writer.writerow(['sku', 'name', 'price'])
        for p in Product.objects.filter(is_active=True).only('sku', 'name', 'price').order_by('sku'):
            writer.writerow([p.sku, p.name, str(p.price)])
        return response
