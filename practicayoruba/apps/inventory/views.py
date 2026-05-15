"""Views — apps.inventory (Sprint 10)."""
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView

from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from apps.settings_app.models import SiteSettings

from .models import StockMovement, StockAlert
from .serializers import (
    StockDashboardSerializer, StockMovementSerializer,
    StockAlertSerializer, StockAdjustSerializer,
)
from .services import InventoryService, _get_stock_status


class InventoryDashboardView(APIView):
    """
    GET /api/v1/admin/inventory/
    Dashboard de inventario con estado NORMAL/BAJO/AGOTADO.
    Filtro opcional ?status=BAJO|AGOTADO|NORMAL.
    UC-INV-01 (FR-INV-01.02).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Dashboard de inventario',
        parameters=[
            OpenApiParameter('status', str,
                             description='Filtrar: NORMAL, BAJO, AGOTADO'),
        ],
        tags=['inventory'],
    )
    def get(self, request):
        threshold = SiteSettings.get_current().min_stock_threshold
        status_filter = request.query_params.get('status', '').upper()
        rows = []

        # Productos con variantes → iterar variantes
        for v in (ProductVariant.objects
                  .filter(product__is_active=True)
                  .select_related('product', 'option', 'option__variant_type')
                  .order_by('product__name', 'option__order')):
            st = _get_stock_status(v.stock, threshold)
            if status_filter and st != status_filter:
                continue
            rows.append({
                'product_id':    v.product.pk,
                'product_name':  v.product.name,
                'sku':           v.sku,
                'variant_id':    v.pk,
                'variant_label': v.option.label,
                'stock':         v.stock,
                'status':        st,
                'threshold':     threshold,
            })

        # Productos sin variantes → usar Product.stock
        products_with_variants = set(
            ProductVariant.objects
            .filter(is_active=True)
            .values_list('product_id', flat=True)
        )
        for p in (Product.objects
                  .filter(is_active=True)
                  .exclude(pk__in=products_with_variants)
                  .order_by('name')):
            st = _get_stock_status(p.stock, threshold)
            if status_filter and st != status_filter:
                continue
            rows.append({
                'product_id':    p.pk,
                'product_name':  p.name,
                'sku':           p.sku,
                'variant_id':    None,
                'variant_label': None,
                'stock':         p.stock,
                'status':        st,
                'threshold':     threshold,
            })

        return Response({
            'threshold': threshold,
            'count': len(rows),
            'results': rows,
        })


class StockAdjustView(APIView):
    """
    POST /api/v1/admin/inventory/<product_pk>/adjust/
    Ajuste manual de stock de un producto (sin variante). UC-INV-04.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Ajuste manual de stock (producto sin variante)',
        tags=['inventory'],
    )
    def post(self, request, product_pk):
        from django.shortcuts import get_object_or_404
        product = get_object_or_404(Product, pk=product_pk, is_active=True)
        s = StockAdjustSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            mov = InventoryService.adjust(
                product=product, variant=None,
                delta=s.validated_data['delta'],
                notes=s.validated_data.get('notes', ''),
                created_by=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc),
                             'codigo_error': 'STOCK_NEGATIVO'}, status=400)
        return Response(StockMovementSerializer(mov).data, status=201)


class VariantStockAdjustView(APIView):
    """
    POST /api/v1/admin/inventory/variants/<variant_pk>/adjust/
    Ajuste manual de stock de una variante. UC-INV-04.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Ajuste manual de stock (variante)',
        tags=['inventory'],
    )
    def post(self, request, variant_pk):
        from django.shortcuts import get_object_or_404
        variant = get_object_or_404(ProductVariant, pk=variant_pk, is_active=True)
        s = StockAdjustSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            mov = InventoryService.adjust(
                product=variant.product, variant=variant,
                delta=s.validated_data['delta'],
                notes=s.validated_data.get('notes', ''),
                created_by=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc),
                             'codigo_error': 'STOCK_NEGATIVO'}, status=400)
        return Response(StockMovementSerializer(mov).data, status=201)


class StockAlertListView(ListAPIView):
    """GET /api/v1/admin/inventory/alerts/ — alertas pendientes. UC-INV-01."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = StockAlertSerializer

    def get_queryset(self):
        return StockAlert.objects.filter(resolved=False).select_related(
            'product', 'variant', 'variant__option'
        )


# =============================================================================
# Sprint 11 — UC-INV-05: Importación masiva de productos desde CSV
# =============================================================================

import csv, io, threading, uuid
from django.core.cache import cache
from django.utils.text import slugify
from rest_framework.parsers import MultiPartParser


IMPORT_JOB_TTL   = 3600   # 1 hora
IMPORT_SYNC_LIMIT = 100   # filas síncronas máximas


def _process_import_csv(content: bytes, user) -> dict:
    """
    Procesa el CSV de importación de productos. UC-INV-05 (FR-INV-05.02).
    Retorna un dict con created, failed y errors.
    Cada fila crea un Product en borrador (is_active=False, is_published=False).
    Tolerante a fallos: si una fila falla, las demás siguen procesándose.
    """
    from apps.catalogue.models import Category, Product
    from .models import StockMovement

    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    reader = csv.DictReader(io.StringIO(text))
    required = {'name', 'sku', 'base_price', 'category_slug'}
    headers = set(reader.fieldnames or [])
    if not required.issubset(headers):
        missing = required - headers
        return {
            'status': 'ERROR',
            'codigo_error': 'ENCABEZADO_INVALIDO',
            'detail': f'Columnas faltantes: {", ".join(sorted(missing))}',
            'created': 0, 'failed': 0, 'errors': [],
        }

    created, failed, errors = 0, 0, []

    for i, row in enumerate(reader, start=2):
        name  = (row.get('name') or '').strip()
        sku   = (row.get('sku') or '').strip().upper()
        price = (row.get('base_price') or '').strip().replace(',', '.')
        cat_slug = (row.get('category_slug') or '').strip()

        if not all([name, sku, price, cat_slug]):
            failed += 1
            errors.append({'line': i, 'sku': sku or '(vacío)',
                           'error': 'Campos obligatorios vacíos.'})
            continue

        try:
            from decimal import Decimal, InvalidOperation
            price_dec = Decimal(price)
            if price_dec <= 0:
                raise ValueError('precio <= 0')
        except Exception:
            failed += 1
            errors.append({'line': i, 'sku': sku,
                           'error': f'Precio inválido: "{price}"'})
            continue

        try:
            cat = Category.objects.get(slug=cat_slug, is_active=True)
        except Category.DoesNotExist:
            failed += 1
            errors.append({'line': i, 'sku': sku,
                           'error': f'Categoría "{cat_slug}" no existe.'})
            continue

        if Product.objects.filter(sku__iexact=sku).exists():
            failed += 1
            errors.append({'line': i, 'sku': sku,
                           'error': f'SKU "{sku}" ya existe en el catálogo.'})
            continue

        # Generar slug único
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while Product.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1

        try:
            Product.objects.create(
                name=name, slug=slug, sku=sku,
                description=row.get('description', '').strip(),
                short_description=row.get('short_description', '').strip(),
                category=cat,
                price=price_dec,
                stock=max(0, int(row.get('stock', 0) or 0)),
                is_active=False, is_published=False,
            )
            created += 1
        except Exception as exc:
            failed += 1
            errors.append({'line': i, 'sku': sku, 'error': str(exc)})

    return {
        'status': 'COMPLETED',
        'created': created,
        'failed': failed,
        'errors': errors[:50],   # máx 50 errores en la respuesta
    }


class ProductImportView(APIView):
    """
    POST /api/v1/admin/inventory/import/
    Importa productos en lote desde CSV. UC-INV-05 (FR-INV-05.02).

    <= 100 filas: respuesta síncrona HTTP 200 con reporte.
    >  100 filas: HTTP 202 con job_id para polling.

    Columnas requeridas: name, sku, base_price, category_slug.
    Opcionales: description, short_description, stock.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes     = [MultiPartParser]

    @extend_schema(
        summary='Importar productos desde CSV',
        description=(
            'Crea productos en borrador (is_active=False). '
            '≤ 100 filas: respuesta inmediata. '
            '> 100 filas: HTTP 202 + job_id para polling. '
            'Columnas: name, sku, base_price, category_slug.'
        ),
        tags=['inventory'],
    )
    def post(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'detail': 'Se requiere el archivo CSV.'}, status=400)

        content = csv_file.read()

        # Contar filas para decidir modo síncrono/asíncrono
        try:
            line_count = content.decode('utf-8-sig', errors='replace').count('\n')
        except Exception:
            line_count = 0

        if line_count <= IMPORT_SYNC_LIMIT:
            # Síncrono
            result = _process_import_csv(content, request.user)
            if result.get('codigo_error') == 'ENCABEZADO_INVALIDO':
                return Response(result, status=400)
            return Response(result, status=200)
        else:
            # Asíncrono — threading + cache
            job_id = str(uuid.uuid4())
            cache.set(f'import_job:{job_id}', {'status': 'PROCESSING',
                                                'created': 0, 'failed': 0},
                      IMPORT_JOB_TTL)

            user = request.user

            def _run():
                result = _process_import_csv(content, user)
                cache.set(f'import_job:{job_id}', result, IMPORT_JOB_TTL)

            t = threading.Thread(target=_run, daemon=True)
            t.start()

            return Response({
                'status': 'PROCESSING',
                'job_id': job_id,
                'message': (
                    f'El archivo tiene más de {IMPORT_SYNC_LIMIT} filas. '
                    f'Usa GET /api/v1/admin/inventory/import/{job_id}/ '
                    f'para consultar el progreso.'
                ),
            }, status=202)


class ProductImportStatusView(APIView):
    """GET /api/v1/admin/inventory/import/<job_id>/ — polling de estado."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Consultar estado de importación CSV',
        tags=['inventory'],
    )
    def get(self, request, job_id):
        result = cache.get(f'import_job:{job_id}')
        if result is None:
            return Response({'detail': 'Job no encontrado o expirado.',
                             'codigo_error': 'JOB_NO_ENCONTRADO'}, status=404)
        return Response(result)
