import csv
import io
import uuid
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
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from .models import Category, Product, SearchHistory
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
        qs = Product.objects.filter(is_active=True, is_published=True).select_related('category')
        category_slug = self.request.query_params.get('category')
        if category_slug:
            pks = _get_category_descendants(category_slug)
            if not pks:
                return Product.objects.none()
            qs = qs.filter(category_id__in=pks)
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
        summary='Ver catálogo de productos',
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
        return Product.objects.filter(is_active=True, is_published=True).select_related('category')

    @extend_schema(summary='Ver detalle de producto', responses={200: ProductDetailSerializer, 404: None}, tags=['catalogue'])
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
        qs = Product.objects.filter(is_active=True, is_published=True).select_related('category')
        qs = _fulltext_search(qs, q)
        if request.query_params.get('category'):
            qs = qs.filter(category_id=request.query_params['category'])
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


class AutocompleteView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Autocomplete de productos',
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

    def perform_destroy(self, instance):
        self._deactivate_category(instance)

    @extend_schema(summary='Desactivar categoría por POST', responses={200: CategoryAdminSerializer, 400: None}, tags=['admin-catalogue'])
    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        instance = self.get_object()
        self._deactivate_category(instance)
        return Response(self.get_serializer(instance).data)

    def _deactivate_category(self, instance):
        if instance.products.filter(is_active=True).exists():
            raise ValidationError({
                'detail': 'No se puede desactivar una categoria con productos activos.',
                'codigo_error': 'CATEGORY_HAS_PRODUCTS',
            })
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])
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

    @extend_schema(summary='Desactivar categoría (soft delete)', responses={204: None, 400: None}, tags=['admin-catalogue'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


def _build_category_tree_with_counts():
    direct_counts = dict(
        Product.objects.filter(is_active=True, is_published=True)
        .values('category_id').annotate(n=Count('id')).values_list('category_id', 'n')
    )
    all_cats = list(Category.objects.filter(is_active=True).prefetch_related('children').order_by('name'))
    cat_map = {c.pk: c for c in all_cats}
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
        summary='Árbol de categorías del catálogo',
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
    queryset           = Product.objects.select_related('category').order_by('-created_at')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

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
        instance = self.get_object()
        old_price = instance.price
        old_category_pk = instance.category_id
        updated = serializer.save()
        if updated.category_id != old_category_pk:
            cache.delete(CATEGORY_TREE_CACHE_KEY)
        if updated.price != old_price:
            ProductPriceHistory.objects.create(
                product=updated, old_price=old_price, new_price=updated.price,
                source=ProductPriceHistory.MANUAL, changed_by=self.request.user,
            )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.is_published = False
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_active', 'is_published', 'is_deleted', 'deleted_at', 'updated_at'])
        cache.delete(f'product:{instance.pk}:detail')
        cache.delete(CATEGORY_TREE_CACHE_KEY)

    @extend_schema(summary='Listar productos (admin)', tags=['admin-catalogue'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Desactivar producto (soft delete)', responses={204: None}, tags=['admin-catalogue'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

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
                'diff_pct': round(float((new_price - product.price) / product.price * 100), 2),
            })
        return validas, invalidas

    def _apply_percentage(self, pct, category_id=None, price_min=None, price_max=None):
        qs = Product.objects.filter(is_active=True).only('id', 'sku', 'price', 'name')
        if category_id:
            qs = qs.filter(category_id=category_id)
        if price_min:
            qs = qs.filter(price__gte=price_min)
        if price_max:
            qs = qs.filter(price__lte=price_max)
        multiplier = Decimal(str(1 + pct / 100))
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
                pct = float(request.data.get('pct', 0))
            except (TypeError, ValueError):
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
        with transaction.atomic():
            for row in validas:
                p = products.get(row['product_id'])
                if not p:
                    continue
                p.price = Decimal(row['new_price'])
                updated.append(p)
            Product.objects.bulk_update(updated, ['price'])
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
