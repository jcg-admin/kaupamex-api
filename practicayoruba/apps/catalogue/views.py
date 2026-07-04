import csv
import io
import uuid
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse
from django.db import transaction, connection
from django.db.models import Q, Count
from apps.catalogue.models import Product
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from django.core.cache import cache
from rest_framework import serializers as rf_serializers, status
from rest_framework.exceptions import ValidationError, NotFound
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.filters import BaseFilterBackend
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from .models import Category, Product, ProductImage, SearchHistory
from .serializers import (
    ProductListSerializer, ProductDetailSerializer, ProductSearchSerializer,
    AutocompleteSerializer, SearchHistorySerializer, CategoryAdminSerializer,
    CategoryWithCountSerializer, ProductAdminSerializer, ProductPriceHistorySerializer,
)
from .models import ProductPriceHistory
from apps.cart.models import CartItem
from apps.wishlist.models import WishlistItem
import logging
"""
Views — apps.catalogue

Sprint 4 — UC-CAT-01
Sprint 5 — UC-CAT-02, UC-CAT-03, UC-CAT-03-EXT, UC-SRCH-01
Sprint 6 — UC-SRCH-02, UC-SRCH-03, UC-CAT-04, UC-CAT-05, UC-CAT-06
"""
import re
import threading



MAX_QUERY_LENGTH = 100
MIN_QUERY_LENGTH = 2
AUTOCOMPLETE_CACHE_TTL   = 60
AUTOCOMPLETE_MAX_RESULTS = 5
CATEGORY_TREE_CACHE_KEY  = 'categories:tree'
CATEGORY_TREE_CACHE_TTL  = 300

logger = logging.getLogger('apps')


def _normalize_query(q: str) -> str:
    q = q.strip()
    q = re.sub(r'\s+', ' ', q)
    return q[:MAX_QUERY_LENGTH]


def _validate_query(q: str) -> str:
    q = _normalize_query(q)
    if len(q) < MIN_QUERY_LENGTH:
        raise ValidationError(
            {'q': f'Ingresa al menos {MIN_QUERY_LENGTH} caracteres para buscar.', 'codigo_error': 'TERMINO_MUY_CORTO'},
            code='TERMINO_MUY_CORTO',
        )
    return q


def _fulltext_search(qs, term: str):
    fulltext_qs = qs.extra(
        select={'relevance': (
            "MATCH(`catalogue_product`.`name`, `catalogue_product`.`description`, "
            "`catalogue_product`.`short_description`) AGAINST (%s IN BOOLEAN MODE)"
        )},
        select_params=[term],
        where=[
            "MATCH(`catalogue_product`.`name`, `catalogue_product`.`description`, "
            "`catalogue_product`.`short_description`) AGAINST (%s IN BOOLEAN MODE)"
        ],
        params=[term],
        order_by=['-is_featured', '-relevance'],
    )
    if fulltext_qs.exists():
        return fulltext_qs
    return qs.filter(
        Q(name__icontains=term) | Q(description__icontains=term) | Q(short_description__icontains=term)
    ).order_by('-is_featured', 'name')


def _get_category_descendants(slug: str) -> set:
    try:
        root = Category.objects.get(slug=slug, is_active=True)
    except Category.DoesNotExist:
        return set()
    return root.get_descendants_ids()


def _resolve_category_pks(slugs):
    """Une los PKs (con descendientes) de una lista de slugs de categoria.

    T-11 / DEC-STF-11: el filtro de categoria acepta multiples valores
    (?category=a&category=b). Retorna None si no se pidio ninguna categoria;
    un set vacio si se pidieron slugs pero ninguno existe/activo — en ese caso
    el caller debe devolver un queryset vacio (no "todos").
    """
    slugs = [s for s in (slugs or []) if s]
    if not slugs:
        return None
    pks = set()
    for slug in slugs:
        pks |= _get_category_descendants(slug)
    return pks


def _build_active_filters(params) -> dict:
    active = {}
    categories = [c for c in params.getlist('category') if c]
    if categories:
        active['category'] = categories
    if params.get('price_min'):
        active['price_min'] = params['price_min']
    if params.get('price_max'):
        active['price_max'] = params['price_max']
    if params.get('in_stock', '').lower() == 'true':
        active['in_stock'] = True
    return active


def _record_history_async(user, term: str) -> None:
    try:
        SearchHistory.record(user=user, term=term)
    except Exception:
        logger.warning('SearchHistory.record falló para user=%s term=%r', getattr(user, 'pk', user), term, exc_info=True)


class CatalogueOrderingFilter(BaseFilterBackend):
    ORDERING_MAP = {
        'novedad': '-created_at', 'precio-asc': 'price', 'precio-desc': '-price',
        'nombre': 'name', 'nombre-desc': '-name',
        'price': 'price', '-price': '-price', 'name': 'name', '-name': '-name',
        '-created_at': '-created_at', 'created_at': 'created_at',
    }
    DEFAULT_ORDERING = ('-created_at',)

    def filter_queryset(self, request, queryset, view):
        param = request.query_params.get('ordering', '').strip()
        if not param:
            return queryset.order_by(*self.DEFAULT_ORDERING)
        mapped = self.ORDERING_MAP.get(param)
        if mapped is None:
            raise ValidationError({
                'ordering': f"'{param}' no es un criterio de ordenamiento válido.",
                'codigo_error': 'INVALID_ORDERING',
                'valores_validos': list(self.ORDERING_MAP.keys()),
            })
        return queryset.order_by(mapped)


class CataloguePagination(PageNumberPagination):
    page_size             = 20
    page_size_query_param = 'page_size'
    max_page_size         = 100


class CatalogueListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class   = ProductListSerializer
    pagination_class   = CataloguePagination
    filter_backends    = [CatalogueOrderingFilter]

    def get_queryset(self):
        # H-CICLO31-04: prefetch images para evitar N+1 en ProductListSerializer.
        # API-1/API-2: prefetch discounts y variants para evitar N+1 en
        # _get_active_discount y get_variants_available.
        qs = (Product.objects.filter(is_active=True, is_published=True)
              .prefetch_related('categories', 'images', 'discounts', 'variants'))
        cat_pks = _resolve_category_pks(self.request.query_params.getlist('category'))
        if cat_pks is not None:
            if not cat_pks:
                return Product.objects.none()
            qs = qs.filter(categories__in=cat_pks).distinct()
        price_min = self.request.query_params.get('price_min')
        if price_min:
            try:
                val = Decimal(price_min)
                # H-CICLO80-04: reject negative prices — Decimal() accepts
                # them silently and produces nonsensical filter results.
                if val < 0:
                    raise ValidationError({'price_min': 'El precio mínimo no puede ser negativo.'})
                qs = qs.filter(price__gte=val)
            except InvalidOperation:
                raise ValidationError({'price_min': 'Valor numérico inválido.'})
        price_max = self.request.query_params.get('price_max')
        if price_max:
            try:
                val = Decimal(price_max)
                # H-CICLO80-04: reject negative prices.
                if val < 0:
                    raise ValidationError({'price_max': 'El precio máximo no puede ser negativo.'})
                qs = qs.filter(price__lte=val)
            except InvalidOperation:
                raise ValidationError({'price_max': 'Valor numérico inválido.'})
        # H-CICLO110-02: aplicar filtro in_stock aqui. Anteriormente solo
        # ProductSearchView aplicaba el filtro; CatalogueListView lo
        # registraba en filters_applied pero no filtraba el queryset, de
        # modo que ?in_stock=true devolvía productos sin stock junto con
        # la clave "in_stock": true en la respuesta — resultado incoherente.
        if self.request.query_params.get('in_stock', '').lower() == 'true':
            qs = qs.filter(stock__gt=0)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        active_filters = _build_active_filters(request.query_params)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['filters_applied'] = active_filters
            return response
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'next': None, 'previous': None,
                         'filters_applied': active_filters, 'results': serializer.data})

    @extend_schema(
        summary='[DEPRECATED → /api/v2/products/] Ver catálogo de productos',
        deprecated=True,
        parameters=[
            OpenApiParameter('category', str),
            OpenApiParameter('price_min', OpenApiTypes.DECIMAL),
            OpenApiParameter('price_max', OpenApiTypes.DECIMAL),
            OpenApiParameter('ordering', str),
        ],
        responses={200: ProductListSerializer(many=True)},
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class ProductDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class   = ProductDetailSerializer
    lookup_field       = 'slug'

    def get_queryset(self):
        # H-CICLO39-01: prefetch images para evitar N+1 en ProductDetailSerializer.
        # ProductDetailSerializer expone `images` (many=True) y llama
        # get_related_products() que instancia ProductListSerializer en 4
        # productos adicionales — cada uno accede a obj.images sin prefetch.
        # Sin prefetch_related('images') la vista dispara 1 + 4 = 5 queries
        # extra de imágenes por cada llamada a GET /api/v1/products/<slug>/.
        return (
            Product.objects
            .filter(is_active=True, is_published=True)
            .prefetch_related('categories', 'images')
        )

    @extend_schema(
        summary='[DEPRECATED → /api/v2/products/<slug>/] Ver detalle de producto',
        deprecated=True,
        responses={200: ProductDetailSerializer, 404: None},
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ProductSearchView(ListAPIView):
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
        q = _validate_query(request.query_params.get('q', ''))
        # H-CICLO31-04: prefetch images para evitar N+1 en ProductSearchSerializer.
        # API-1/API-2: prefetch discounts y variants para evitar N+1 en
        # _get_active_discount y get_variants_available.
        qs = (Product.objects.filter(is_active=True, is_published=True)
              .prefetch_related('categories', 'images', 'discounts', 'variants'))
        qs = _fulltext_search(qs, q)
        if request.query_params.get('category'):
            try:
                category_pk = int(request.query_params['category'])
            except (ValueError, TypeError):
                raise ValidationError({'category': 'El ID de categoría debe ser un entero.'})
            qs = qs.filter(categories__id=category_pk).distinct()
        price_min = request.query_params.get('price_min')
        if price_min:
            try:
                val = Decimal(price_min)
                # H-CICLO80-04: reject negative prices — same fix as
                # CatalogueListView.get_queryset().
                if val < 0:
                    raise ValidationError({'price_min': 'El precio mínimo no puede ser negativo.'})
                qs = qs.filter(price__gte=val)
            except InvalidOperation:
                raise ValidationError({'price_min': 'Valor numérico inválido.'})
        price_max = request.query_params.get('price_max')
        if price_max:
            try:
                val = Decimal(price_max)
                # H-CICLO80-04: reject negative prices.
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
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['active_filters'] = active_filters
            return response
        serializer = self.get_serializer(qs, many=True)
        return Response({'count': qs.count(), 'next': None, 'previous': None,
                         'active_filters': active_filters, 'results': serializer.data})

    @extend_schema(
        summary='[DEPRECATED → /api/v2/products/?q=] Buscar productos',
        deprecated=True,
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


class AutocompleteView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='[DEPRECATED → /api/v2/products/?q=&autocomplete=1] Autocomplete',
        deprecated=True,
        parameters=[OpenApiParameter('q', str, required=True)],
        responses={200: AutocompleteSerializer(many=True)},
        tags=['catalogue'],
    )
    def get(self, request):
        prefijo = _normalize_query(request.query_params.get('q', '').strip())
        if len(prefijo) < MIN_QUERY_LENGTH:
            return Response([])
        cache_key = f'autocomplete:{prefijo.lower().replace(" ", "_")}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        qs = (Product.objects.filter(name__istartswith=prefijo, is_active=True, is_published=True)
              .only('id', 'name', 'slug').order_by('name')[:AUTOCOMPLETE_MAX_RESULTS])
        data = AutocompleteSerializer(qs, many=True).data
        cache.set(cache_key, data, AUTOCOMPLETE_CACHE_TTL)
        return Response(data)


class SearchHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Ver historial de búsquedas', responses={200: SearchHistorySerializer(many=True)}, tags=['catalogue'])
    def get(self, request):
        return Response(SearchHistorySerializer(SearchHistory.objects.filter(user=request.user), many=True).data)

    @extend_schema(summary='Borrar todo el historial', responses={204: None}, tags=['catalogue'],
                   operation_id='catalogue_search_history_clear_all')
    def delete(self, request):
        SearchHistory.objects.filter(user=request.user).delete()
        return Response(status=204)


class SearchHistoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Borrar una entrada del historial', responses={204: None, 404: None}, tags=['catalogue'],
                   operation_id='catalogue_search_history_entry_destroy')
    def delete(self, request, pk):
        try:
            SearchHistory.objects.get(pk=pk, user=request.user).delete()
        except SearchHistory.DoesNotExist:
            raise NotFound('Entrada no encontrada.')
        return Response(status=204)


class CategoryAdminViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = CategoryAdminSerializer
    queryset           = Category.objects.all().order_by('name')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']
    # H-CICLO104-02b: paginar la lista de categorias para evitar respuesta
    # sin limite si el catalogo crece a cientos de categorias.
    pagination_class   = CataloguePagination

    def perform_destroy(self, instance):
        self._deactivate_category(instance)

    @extend_schema(summary='Desactivar categoría por POST', responses={200: CategoryAdminSerializer, 400: None}, tags=['admin-catalogue'])
    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        instance = self.get_object()
        self._deactivate_category(instance)
        return Response(self.get_serializer(instance).data)

    def _deactivate_category(self, instance):
        # H-CICLO104-02: envolver en transaction.atomic() + select_for_update()
        # para serializar solicitudes concurrentes y evitar que dos admins
        # desactiven la misma categoria simultaneamente con estado inconsistente.
        # Ademas verificar productos activos en TODAS las subcategorias (no solo
        # las directas): un arbol de categorias puede tener productos en
        # descendientes que quedaban activos si solo se revisaba el nivel raiz.
        with transaction.atomic():
            locked = Category.objects.select_for_update().get(pk=instance.pk)
            all_desc_ids = locked.get_descendants_ids()
            if Product.objects.filter(
                categories__in=all_desc_ids, is_active=True
            ).exists():
                raise ValidationError({
                    'detail': (
                        'No se puede desactivar una categoria (o sus subcategorias) '
                        'que tenga productos activos.'
                    ),
                    'codigo_error': 'CATEGORY_HAS_PRODUCTS',
                })
            # Soft-desactivar tambien todos los descendientes para que el arbol
            # quede consistente (padre inactivo => hijos inactivos).
            Category.objects.filter(id__in=all_desc_ids).update(
                is_active=False, updated_at=timezone.now()
            )
        instance.refresh_from_db()
        self._invalidate_category_cache()

    def perform_create(self, serializer):
        serializer.save()
        self._invalidate_category_cache()

    def perform_update(self, serializer):
        serializer.save()
        self._invalidate_category_cache()

    def _invalidate_category_cache(self):
        cache.delete(CATEGORY_TREE_CACHE_KEY)

    @extend_schema(summary='Listar categorías (admin)', tags=['admin-catalogue'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear categoría', tags=['admin-catalogue'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar categoría', tags=['admin-catalogue'])
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Reordenar categorías hermanas',
        description=(
            'UC-CAT-15: recibe {"parent": <id|null>, "order": [id, ...]} con los '
            'IDs de las categorías hijas de `parent` en el nuevo orden y persiste '
            'Category.order = índice. Reordena solo entre hermanos del mismo padre; '
            'mover a otro padre se hace con PATCH parent_id (con validación de ciclo).'
        ),
        responses={200: None, 400: None},
        tags=['admin-catalogue'],
    )
    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        parent_id = request.data.get('parent')
        ids = request.data.get('order')
        if not isinstance(ids, list) or not ids:
            return Response(
                {'detail': 'Se requiere "order": lista no vacía de IDs de categoría.',
                 'codigo_error': 'ORDER_INVALIDO'},
                status=400,
            )
        siblings = set(
            Category.objects.filter(parent_id=parent_id).values_list('id', flat=True)
        )
        # Reorden completo entre hermanos: el set enviado debe coincidir con los
        # hijos del padre indicado (sin faltantes, extras ni duplicados).
        if set(ids) != siblings or len(ids) != len(siblings):
            return Response(
                {'detail': 'Los IDs no coinciden con las categorías hijas de ese padre.',
                 'codigo_error': 'ORDER_IDS_NO_COINCIDEN'},
                status=400,
            )
        with transaction.atomic():
            for index, cat_id in enumerate(ids):
                Category.objects.filter(pk=cat_id, parent_id=parent_id).update(
                    order=index, updated_at=timezone.now(),
                )
        self._invalidate_category_cache()
        return Response({'detail': 'Orden actualizado.', 'count': len(ids)})

    @extend_schema(summary='Desactivar categoría (soft delete)', responses={204: None, 400: None}, tags=['admin-catalogue'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


def _build_category_tree_with_counts():
    direct_counts = dict(
        Product.objects.filter(is_active=True, is_published=True)
        .values('categories').annotate(n=Count('id')).values_list('categories', 'n')
    )
    all_cats = list(Category.objects.filter(is_active=True).order_by('name'))
    cat_map = {c.pk: c for c in all_cats}

    # H-CICLO77-01: populate prefetch cache for every category in cat_map so
    # that CategoryWithCountSerializer.get_children() can call
    # obj.children.all() at any depth without hitting the database.
    # Previously, prefetch_related('children') only populated the cache on
    # the root-level objects; child objects at depth 2+ had no cache entry,
    # causing N+1 queries for each grandchild lookup on cache miss.
    children_by_parent = {}
    for c in all_cats:
        if c.parent_id is not None:
            children_by_parent.setdefault(c.parent_id, []).append(c)
    for c in all_cats:
        c._prefetched_objects_cache = getattr(c, '_prefetched_objects_cache', {})
        c._prefetched_objects_cache['children'] = children_by_parent.get(c.pk, [])

    accumulated = {c.pk: direct_counts.get(c.pk, 0) for c in all_cats}

    def _accumulate(cat_pk):
        total = accumulated[cat_pk]
        for child in cat_map[cat_pk].children.all():
            if child.pk in accumulated:
                total += _accumulate(child.pk)
        accumulated[cat_pk] = total
        return total

    for root in [c for c in all_cats if c.parent_id is None]:
        _accumulate(root.pk)
    for cat in all_cats:
        cat.product_count = accumulated[cat.pk]
    return [c for c in all_cats if c.parent_id is None]


class CategoryListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='[DEPRECATED → /api/v2/categories/] Árbol de categorías',
        deprecated=True,
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


def _count_active_carts(product):
    try:
        return CartItem.objects.filter(product=product).count()
    except Exception:
        logger.warning('_count_active_carts failed for product %s', product.pk, exc_info=True)
        return 0


def _count_wishlist_items(product):
    try:
        return WishlistItem.objects.filter(product=product).count()
    except Exception:
        logger.warning('_count_wishlist_items failed for product %s', product.pk, exc_info=True)
        return 0


class ProductDeactivateAction:
    @action(detail=True, methods=['post'], url_path='deactivate')
    @extend_schema(
        summary='Desactivar producto con preview de impacto',
        responses={200: OpenApiResponse(description='Preview o confirmacion.'), 400: OpenApiResponse(description='Ya desactivado.')},
        tags=['admin-catalogue'],
    )
    def deactivate(self, request, pk=None):
        product = self.get_object()
        if not product.is_active:
            return Response({'detail': 'El producto ya está desactivado.', 'codigo_error': 'PRODUCTO_YA_INACTIVO'}, status=400)
        impact = {
            'product_id': product.pk, 'product_name': product.name,
            'stock': product.stock, 'active_carts': _count_active_carts(product),
            'wishlists': _count_wishlist_items(product),
        }
        if not request.data.get('confirm', False):
            impact['message'] = 'Envía {"confirm": true} para confirmar la desactivación.'
            return Response(impact, status=200)
        product.is_active = False
        product.is_published = False
        product.save(update_fields=['is_active', 'is_published', 'updated_at'])
        cache.delete(f'product:{product.pk}:detail')
        cache.delete(CATEGORY_TREE_CACHE_KEY)
        return Response({**impact, 'is_active': False, 'message': 'Producto desactivado correctamente.'}, status=200)


class ProductAdminViewSet(ProductDeactivateAction, ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = ProductAdminSerializer
    # H-CICLO47-01: prefetch_related('images') evita N+1 al serializar con
    # ProductAdminSerializer, que expone el campo `images` (many=True).
    # API-1/API-2: prefetch discounts y variants para evitar N+1 en
    # _get_active_discount y get_variants_available.
    queryset           = Product.objects.prefetch_related('categories', 'images', 'discounts', 'variants').order_by('-created_at')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']
    # H-CICLO38-02: CatalogueListView (buyer) usa CataloguePagination
    # (page_size=20). Sin pagination_class, ProductAdminViewSet devuelve
    # TODOS los productos como lista plana — N consultas, respuesta
    # potencialmente enorme en producción con cientos de productos.
    # adminSlice.fetchAdminProducts ya tolera ambos formatos (results ?? payload)
    # por lo que añadir paginación es retrocompatible para el frontend.
    pagination_class   = CataloguePagination

    def get_queryset(self):
        """Aplica los filtros de listado del panel admin.

        H-ADMIN-FILTER: antes esta vista solo declaraba un ``queryset``
        estático sin ``get_queryset`` ni filter backends, así que los chips
        "Publicados" / "Borradores" / "Sin stock" y la caja de búsqueda del UI
        (``?filter=`` y ``?search=``) se ignoraban por completo: cualquier
        filtro devolvía el catálogo entero. El manager por defecto ya excluye
        ``is_deleted=True`` (SoftDeleteModel); los productos solo desactivados
        (``is_active=False``) sí aparecen y se reactivan vía ``activate``.
        """
        qs = super().get_queryset()
        params = self.request.query_params
        estado = params.get('filter', 'all')
        if estado == 'published':
            qs = qs.filter(is_published=True)
        elif estado == 'draft':
            qs = qs.filter(is_published=False)
        elif estado == 'out_of_stock':
            qs = qs.filter(stock__lte=0)
        search = (params.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
        return qs

    def _check_sku_unique(self, sku, exclude_pk=None):
        if not sku:
            return False
        qs = Product.objects.filter(sku=sku.upper())
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()

    def create(self, request, *args, **kwargs):
        sku = (request.data.get('sku') or '').strip().upper()
        if sku and self._check_sku_unique(sku):
            return Response({'detail': 'Ya existe un producto con ese SKU.', 'codigo_error': 'SKU_DUPLICATE'}, status=409)
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        sku = (request.data.get('sku') or '').strip().upper()
        if sku and self._check_sku_unique(sku, exclude_pk=instance.pk):
            return Response({'detail': 'Ya existe un producto con ese SKU.', 'codigo_error': 'SKU_DUPLICATE'}, status=409)
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        old_price = serializer.instance.price
        updated = serializer.save()
        if updated.price != old_price:
            ProductPriceHistory.objects.create(
                product=updated, old_price=old_price, new_price=updated.price,
                source=ProductPriceHistory.MANUAL, changed_by=self.request.user,
            )
        if 'categories' in serializer.validated_data:
            cache.delete(CATEGORY_TREE_CACHE_KEY)

    def perform_destroy(self, instance):
        with transaction.atomic():
            instance.is_active = False
            instance.is_published = False
            instance.is_deleted = True
            instance.deleted_at = timezone.now()
            instance.save(update_fields=['is_active', 'is_published', 'is_deleted', 'deleted_at', 'updated_at'])
            # H-CICLO84-01: limpiar CartItems y WishlistItems huerfanos.
            # Antes del fix, hacer soft-delete de un producto dejaba filas
            # en cart_cart_item y wishlist_item apuntando a un producto
            # is_deleted=True. Esos registros nunca se limpiaban: el carrito
            # mostraba items "fantasma" y la wishlist retenia referencias
            # invalidas hasta que el usuario las eliminara manualmente.
            CartItem.objects.filter(product=instance).delete()
            WishlistItem.objects.filter(product=instance).delete()
        cache.delete(f'product:{instance.pk}:detail')
        cache.delete(CATEGORY_TREE_CACHE_KEY)

    @extend_schema(summary='Listar productos (admin)', tags=['admin-catalogue'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Desactivar producto (soft delete)', responses={204: None}, tags=['admin-catalogue'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='activate')
    @extend_schema(
        summary='Reactivar producto (revertir desactivación)',
        description=(
            'H-ADMIN-RESTORE: el UI ofrecía "Reactivar producto" '
            '(AdminProductEditPage) y despachaba POST '
            '/api/v2/admin/products/:id/activate/, pero la ruta no existía: solo '
            'estaba deactivate. El botón pegaba a un endpoint inexistente y '
            'devolvía 404 ("Request failed / not found"). Este endpoint es la '
            'contraparte de deactivate: vuelve a marcar is_active=True. La '
            'publicación (is_published) queda como estaba — se controla aparte.'
        ),
        responses={200: ProductAdminSerializer, 400: OpenApiResponse(description='Ya activo.')},
        tags=['admin-catalogue'],
    )
    def activate(self, request, pk=None):
        product = self.get_object()
        if product.is_active:
            return Response(
                {'detail': 'El producto ya está activo.', 'codigo_error': 'PRODUCTO_YA_ACTIVO'},
                status=400,
            )
        product.is_active = True
        product.save(update_fields=['is_active', 'updated_at'])
        cache.delete(f'product:{product.pk}:detail')
        cache.delete(CATEGORY_TREE_CACHE_KEY)
        return Response(self.get_serializer(product).data)

    @action(detail=True, methods=['get'], url_path='price-history')
    @extend_schema(summary='Historial de precios del producto', tags=['admin-catalogue'])
    def price_history(self, request, pk=None):
        product = self.get_object()
        qs = ProductPriceHistory.objects.filter(product=product).order_by('-created_at')
        paginator = CataloguePagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(ProductPriceHistorySerializer(page, many=True).data)
        return Response({'count': qs.count(), 'results': ProductPriceHistorySerializer(qs, many=True).data})

    @action(detail=True, methods=['post'], url_path='toggle-featured')
    @extend_schema(
        summary='Destacar / quitar destacado de un producto',
        description=(
            'Alterna el campo is_featured del producto. '
            'H-CICLO30-03: el endpoint faltaba; el UI llamaba POST y recibía 404.'
        ),
        responses={200: ProductAdminSerializer},
        tags=['admin-catalogue'],
    )
    def toggle_featured(self, request, pk=None):
        product = self.get_object()
        product.is_featured = not product.is_featured
        product.save(update_fields=['is_featured', 'updated_at'])
        cache.delete(f'product:{product.pk}:detail')
        return Response(self.get_serializer(product).data)

    @action(detail=True, methods=['post'], url_path='reorder-images')
    @extend_schema(
        summary='Reordenar imágenes de un producto',
        description=(
            'UC-CAT-16: recibe {"order": [id, id, ...]} con los IDs de imagen '
            'en el nuevo orden y persiste ProductImage.order = índice. El campo '
            'order ya existía (Meta.ordering=[order, id]); faltaba el endpoint '
            'para persistir un reordenamiento por drag-and-drop desde el admin.'
        ),
        responses={200: ProductAdminSerializer},
        tags=['admin-catalogue'],
    )
    def reorder_images(self, request, pk=None):
        product = self.get_object()
        ids = request.data.get('order')
        if not isinstance(ids, list) or not ids:
            return Response(
                {'detail': 'Se requiere "order": lista no vacía de IDs de imagen.',
                 'codigo_error': 'ORDER_INVALIDO'},
                status=400,
            )
        image_ids = set(product.images.values_list('id', flat=True))
        # Reorden completo: el set enviado debe coincidir exactamente con las
        # imágenes del producto (sin faltantes, extras ni duplicados).
        if set(ids) != image_ids or len(ids) != len(image_ids):
            return Response(
                {'detail': 'Los IDs no coinciden con las imágenes del producto.',
                 'codigo_error': 'ORDER_IDS_NO_COINCIDEN'},
                status=400,
            )
        with transaction.atomic():
            for index, image_id in enumerate(ids):
                ProductImage.objects.filter(pk=image_id, product=product).update(order=index)
        cache.delete(f'product:{product.pk}:detail')
        return Response(self.get_serializer(product).data)

    @action(detail=True, methods=['patch'], url_path='images')
    @extend_schema(
        summary='Editar metadata de imágenes en lote (FieldArray)',
        description=(
            'UC-CAT-17: recibe {"images": [{"id", "alt_text"?, "is_cover"?}, ...]} '
            'y actualiza en lote la metadata de las imágenes del producto, como un '
            'FieldArray editable en el admin. NO sube archivos (eso es multipart '
            'aparte por imagen); edita el set existente y mantiene la invariante '
            'de una sola portada (is_cover). El orden se gestiona en reorder-images.'
        ),
        responses={200: ProductAdminSerializer},
        tags=['admin-catalogue'],
    )
    def update_images(self, request, pk=None):
        product = self.get_object()
        items = request.data.get('images')
        if not isinstance(items, list) or not items:
            return Response(
                {'detail': 'Se requiere "images": lista no vacía de {id, ...}.',
                 'codigo_error': 'IMAGES_INVALIDO'},
                status=400,
            )
        image_ids = set(product.images.values_list('id', flat=True))
        sent_ids, covers = [], 0
        for it in items:
            if not isinstance(it, dict) or 'id' not in it:
                return Response(
                    {'detail': 'Cada item requiere "id".',
                     'codigo_error': 'IMAGE_ITEM_INVALIDO'},
                    status=400,
                )
            if it['id'] not in image_ids:
                return Response(
                    {'detail': f'La imagen {it["id"]} no pertenece al producto.',
                     'codigo_error': 'IMAGE_NO_PERTENECE'},
                    status=400,
                )
            sent_ids.append(it['id'])
            if it.get('is_cover') is True:
                covers += 1
        if len(set(sent_ids)) != len(sent_ids):
            return Response(
                {'detail': 'IDs de imagen duplicados en el payload.',
                 'codigo_error': 'IMAGE_IDS_DUPLICADOS'},
                status=400,
            )
        if covers > 1:
            return Response(
                {'detail': 'Solo una imagen puede ser portada (is_cover).',
                 'codigo_error': 'MULTIPLES_PORTADAS'},
                status=400,
            )
        with transaction.atomic():
            for it in items:
                fields = {}
                if 'alt_text' in it:
                    fields['alt_text'] = (it.get('alt_text') or '')[:200]
                if 'is_cover' in it:
                    fields['is_cover'] = bool(it.get('is_cover'))
                if fields:
                    ProductImage.objects.filter(pk=it['id'], product=product).update(**fields)
            # Invariante: al marcar una portada, desmarcar las demás.
            cover_id = next((it['id'] for it in items if it.get('is_cover') is True), None)
            if cover_id is not None:
                product.images.exclude(pk=cover_id).update(is_cover=False)
        cache.delete(f'product:{product.pk}:detail')
        return Response(self.get_serializer(product).data)


PRICE_SYNC_CACHE_TTL = 600


class ProductPriceSyncView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = rf_serializers.Serializer

    def _parse_csv(self, file_obj):
        try:
            content = file_obj.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            content = file_obj.read().decode('latin-1')
        reader = csv.DictReader(io.StringIO(content))
        if not {'sku', 'price'}.issubset(set(reader.fieldnames or [])):
            return [], [{'sku': '', 'error': 'El CSV debe tener columnas "sku" y "price"', 'line': 0}]
        validas, invalidas = [], []
        sku_index = {p.sku.upper(): p for p in Product.objects.filter(is_active=True).only('id', 'sku', 'price', 'name')}
        for i, row in enumerate(reader, start=2):
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
                'sku': sku, 'product_id': product.pk, 'product_name': product.name,
                'old_price': str(product.price), 'new_price': str(new_price),
                'diff_pct': float(((new_price - product.price) / product.price * Decimal('100')).quantize(Decimal('0.01'))),
            })
        return validas, invalidas

    def _apply_percentage(self, pct, category_id=None, price_min=None, price_max=None):
        qs = Product.objects.filter(is_active=True).only('id', 'sku', 'price', 'name')
        if category_id:
            qs = qs.filter(categories__id=category_id).distinct()
        if price_min:
            qs = qs.filter(price__gte=price_min)
        if price_max:
            qs = qs.filter(price__lte=price_max)
        # H-CICLO114-02: pct ya llega como Decimal desde el caller; usar
        # Decimal aritmética pura para evitar float→Decimal precision loss.
        pct_d = Decimal(str(pct)) if not isinstance(pct, Decimal) else pct
        multiplier = Decimal('1') + pct_d / Decimal('100')
        return [{
            'sku': p.sku, 'product_id': p.pk, 'product_name': p.name,
            'old_price': str(p.price),
            'new_price': str(max(Decimal('0.01'), (p.price * multiplier).quantize(Decimal('0.01')))),
            'diff_pct': pct,
        } for p in qs], []

    @extend_schema(summary='Preview de sincronización de precios', responses={200: OpenApiTypes.OBJECT, 400: None}, tags=['admin-catalogue'])
    def post(self, request):
        mode = request.data.get('mode', 'csv')
        if mode == 'percentage':
            try:
                # H-CICLO114-02: usar Decimal para pct desde el origen para que
                # _apply_percentage construya el multiplicador sin perdida de
                # precision por conversion float→Decimal.
                pct = Decimal(str(request.data.get('pct', 0)))
            except Exception:
                return Response({'detail': 'pct debe ser un número.'}, status=400)
            validas, invalidas = self._apply_percentage(
                pct, request.data.get('category_id'),
                request.data.get('price_min'), request.data.get('price_max'),
            )
        else:
            csv_file = request.FILES.get('file')
            if not csv_file:
                return Response({'detail': 'Se requiere el archivo CSV.'}, status=400)
            validas, invalidas = self._parse_csv(csv_file)
        session_id = str(uuid.uuid4())
        cache.set(f'price_sync:{session_id}', validas, PRICE_SYNC_CACHE_TTL)
        return Response({
            'session_id': session_id, 'valid_count': len(validas),
            'invalid_count': len(invalidas), 'preview': validas[:50], 'errors': invalidas,
            'message': f'{len(validas)} precios listos para actualizar.',
        })


class ProductPriceSyncConfirmView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = rf_serializers.Serializer

    @extend_schema(summary='Confirmar sincronización de precios', responses={200: OpenApiTypes.OBJECT, 400: None}, tags=['admin-catalogue'])
    def post(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'detail': 'session_id requerido.'}, status=400)
        validas = cache.get(f'price_sync:{session_id}')
        if validas is None:
            return Response({'detail': 'Sesión expirada o no encontrada.', 'codigo_error': 'SESSION_EXPIRED'}, status=400)
        _logger = logging.getLogger('apps')
        product_ids = [row['product_id'] for row in validas]
        products = {p.pk: p for p in Product.objects.filter(pk__in=product_ids)}
        updated = []
        # H-CICLO30-02: el bulk_update anterior omitía crear entradas en
        # ProductPriceHistory, dejando sin rastro de auditoría los cambios
        # masivos de precio. Se crea una entrada por cada producto afectado.
        history_entries = []
        # H-CICLO44-01: bulk_update bypasses auto_now=True — setear updated_at
        # explicitamente en cada objeto antes de llamar a bulk_update para que
        # el campo refleje el momento real de la actualizacion masiva de precios.
        now = timezone.now()
        with transaction.atomic():
            for row in validas:
                p = products.get(row['product_id'])
                if not p:
                    continue
                old_price = p.price
                p.price = Decimal(row['new_price'])
                p.updated_at = now
                updated.append(p)
                if p.price != old_price:
                    history_entries.append(ProductPriceHistory(
                        product=p,
                        old_price=old_price,
                        new_price=p.price,
                        source=ProductPriceHistory.PRICE_SYNC,
                        changed_by=request.user,
                    ))
            Product.objects.bulk_update(updated, ['price', 'updated_at'])
            if history_entries:
                ProductPriceHistory.objects.bulk_create(history_entries)
        cache.delete_many([f'product:{p.pk}:detail' for p in updated])
        cache.delete(f'price_sync:{session_id}')
        _logger.info('price_sync: %d productos actualizados por %s', len(updated), request.user.username)
        return Response({'updated_count': len(updated), 'message': f'{len(updated)} precios actualizados correctamente.'})


class ProductPriceSyncTemplateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = rf_serializers.Serializer

    @extend_schema(summary='Descargar plantilla CSV de precios',
                   responses={200: OpenApiResponse(description='CSV template.', response=OpenApiTypes.BINARY)},
                   tags=['admin-catalogue'])
    def get(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="price-template.csv"'
        response.write('﻿')
        writer = csv.writer(response)
        writer.writerow(['sku', 'name', 'price'])
        for p in Product.objects.filter(is_active=True).only('sku', 'name', 'price').order_by('sku'):
            writer.writerow([p.sku, p.name, str(p.price)])
        return response


# ─── Catalog CSV Import (UC-CAT-IMPORT) ──────────────────────────────────────

_CATALOG_CSV_MAX_SIZE = 5 * 1024 * 1024  # 5 MB

_CATALOG_ALLOWED_CONTENT_TYPES = {
    'text/csv', 'text/plain', 'application/csv', 'application/vnd.ms-excel',
}


def _process_catalog_csv(file_obj, admin_user):
    """
    Parse and persist a catalog CSV with optional image references.

    CSV columns: name, sku, base_price, category_slug, [description], [image_files]
    image_files: semicolon-separated filenames pre-staged at MEDIA_ROOT/products/images/.

    Products are persisted atomically (all-or-nothing). Image files that don't
    exist on disk produce a warning but do not block import.

    Returns (result_dict, None) on success or (None, error_dict) on failure.
    """
    REQUIRED_HEADERS = {'name', 'sku', 'base_price', 'category_slug'}
    try:
        content = file_obj.read()
        reader = csv.DictReader(io.TextIOWrapper(io.BytesIO(content), encoding='utf-8'))
        headers = set(reader.fieldnames or [])
    except UnicodeDecodeError:
        return None, {
            'status_code': 400,
            'detail': 'El archivo debe estar codificado en UTF-8.',
            'codigo_error': 'CSV_ENCODING_ERROR',
        }
    except Exception:
        return None, {
            'status_code': 400,
            'detail': 'No se pudo leer el archivo CSV.',
            'codigo_error': 'CSV_READ_ERROR',
        }

    if not REQUIRED_HEADERS <= headers:
        missing = sorted(REQUIRED_HEADERS - headers)
        return None, {
            'status_code': 422,
            'detail': f'Encabezados inválidos. Faltan: {missing}',
            'codigo_error': 'CSV_INVALID_HEADERS',
        }

    media_images = Path(settings.MEDIA_ROOT) / 'products' / 'images'
    to_create = []
    error_report = []

    for i, row in enumerate(list(reader), start=2):
        try:
            sku = row.get('sku', '').strip()
            name = row.get('name', '').strip()
            base_price = row.get('base_price', '').strip()
            category_slug = row.get('category_slug', '').strip()
            if not sku:
                raise ValueError('SKU vacío')
            if not name:
                raise ValueError('name vacío')
            if not category_slug:
                raise ValueError('category_slug vacío')
            try:
                price = Decimal(base_price)
                if price.is_nan() or price.is_infinite():
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                raise ValueError(f'Precio inválido: {base_price!r}')
            description = row.get('description', '').strip()
            raw_images = row.get('image_files', '').strip()
            image_files = [f.strip() for f in raw_images.split(';') if f.strip()] if raw_images else []
            to_create.append((i, name, sku, price, category_slug, description, image_files))
        except Exception as exc:
            error_report.append({'row': i, 'reason': str(exc)})

    if error_report:
        return None, {
            'status_code': 422,
            'detail': 'Errores de validación en el CSV.',
            'codigo_error': 'CSV_ROW_ERRORS',
            'errors': error_report,
        }

    created = updated = 0
    warnings = []

    with transaction.atomic():
        for row_num, name, sku, price, cat_slug, desc, images in to_create:
            cat, _ = Category.objects.get_or_create(
                slug=cat_slug,
                defaults={'name': cat_slug, 'is_active': True},
            )
            product, was_created = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    'name': name,
                    'slug': sku.lower().replace(' ', '-'),
                    'description': desc,
                    'price': price,
                    'is_active': True,
                    'is_published': True,
                    'stock': 1,
                },
            )
            product.categories.add(cat)
            if was_created:
                created += 1
            else:
                updated += 1

            for idx, filename in enumerate(images):
                if not (media_images / filename).exists():
                    warnings.append(
                        f'Fila {row_num}: imagen no encontrada en MEDIA_ROOT: {filename}'
                    )
                ProductImage.objects.update_or_create(
                    product=product,
                    order=idx,
                    defaults={
                        'image': f'products/images/{filename}',
                        'alt_text': name[:200],
                        'is_cover': idx == 0,
                    },
                )

    return {'creados': created, 'actualizados': updated, 'advertencias': warnings}, None


class CatalogImportCSVView(APIView):
    """Importar catálogo (productos + imágenes) desde CSV. UC-CAT-IMPORT."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Importar catálogo con imágenes desde CSV',
        tags=['admin-catalogue'],
        request=inline_serializer('CatalogImportRequest', {
            'file': rf_serializers.FileField(),
        }),
        responses={
            201: inline_serializer('CatalogImportResponse', {
                'creados': rf_serializers.IntegerField(),
                'actualizados': rf_serializers.IntegerField(),
                'advertencias': rf_serializers.ListField(child=rf_serializers.CharField()),
            }),
            400: None,
            422: None,
        },
    )
    def post(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response(
                {'detail': 'El archivo CSV es requerido.', 'codigo_error': 'FILE_REQUIRED'},
                status=400,
            )
        file_name = csv_file.name or ''
        if not file_name.lower().endswith('.csv'):
            return Response(
                {'detail': 'Solo se admiten archivos .csv.', 'codigo_error': 'FILE_TYPE_INVALID'},
                status=400,
            )
        ct = (csv_file.content_type or '').split(';')[0].strip()
        if ct and ct not in _CATALOG_ALLOWED_CONTENT_TYPES:
            return Response(
                {'detail': 'Tipo de contenido no permitido. Use text/csv.', 'codigo_error': 'FILE_TYPE_INVALID'},
                status=400,
            )
        if csv_file.size > _CATALOG_CSV_MAX_SIZE:
            return Response(
                {
                    'detail': f'El archivo supera el límite de {_CATALOG_CSV_MAX_SIZE // (1024 * 1024)} MB.',
                    'codigo_error': 'FILE_TOO_LARGE',
                },
                status=400,
            )
        result, error = _process_catalog_csv(csv_file, request.user)
        if error:
            return Response(
                {'detail': error['detail'], 'codigo_error': error['codigo_error']},
                status=error['status_code'],
            )
        return Response(result, status=201)


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
            OpenApiParameter('category', str, description='Category slug; repeatable (?category=a&category=b) to filter by several categories (union, includes descendants).'),
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
        # T-11 / DEC-STF-11: el modo busqueda acepta los mismos slugs que el
        # modo lista (antes exigia un ID entero — inconsistente con el resto
        # del catalogo y con el UI, que siempre usa slugs). Multi-categoria.
        cat_pks = _resolve_category_pks(request.query_params.getlist('category'))
        if cat_pks is not None:
            qs = qs.filter(categories__in=cat_pks).distinct() if cat_pks else qs.none()
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
            response.data['normalized_query'] = q
            return response
        serializer = ProductSearchSerializer(qs, many=True, context=self.get_serializer_context())
        return Response({
            'count': qs.count(),
            'next': None,
            'previous': None,
            'active_filters': active_filters,
            'normalized_query': q,
            'results': serializer.data,
        })
