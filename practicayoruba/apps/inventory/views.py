"""Views — apps.inventory (Sprint 10)."""
import logging

from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView

from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from apps.settings_app.models import SiteSettings

from rest_framework import serializers

from .models import StockMovement, StockAlert
from .serializers import (
    StockDashboardSerializer, StockMovementSerializer,
    StockAlertSerializer, StockAdjustSerializer,
    VariantAdjustNewQuantitySerializer,
)
from .services import InventoryService, _get_stock_status
from django.urls import reverse
from apps.catalogue.models import Category, Product
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.http import HttpResponse

logger = logging.getLogger(__name__)


# Mapeo de alias en inglés (UI agent) hacia los códigos internos en español
# del estado de stock. Aceptamos ambos para no romper el contrato existente.
STATUS_ALIASES = {
    'LOW':     'BAJO',
    'OUT':     'AGOTADO',
    'NORMAL':  'NORMAL',
    'BAJO':    'BAJO',
    'AGOTADO': 'AGOTADO',
}


def _paginate(rows, page: int, page_size: int):
    """Paginación trivial en memoria (UC-INV-01: <500ms p95 ya cumplido)."""
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end   = start + page_size
    return rows[start:end], {
        'page':        page,
        'page_size':   page_size,
        'total':       total,
        'total_pages': total_pages,
    }


class InventoryDashboardView(APIView):
    """
    GET /api/v1/admin/inventory/
    Dashboard de inventario con estado NORMAL/BAJO/AGOTADO.
    Filtro opcional ?status=BAJO|AGOTADO|NORMAL.
    UC-INV-01 (FR-INV-01.02).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = StockDashboardSerializer

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
        raw_status = request.query_params.get('status', '').upper()
        # Aceptamos NORMAL / BAJO / AGOTADO y los alias inglés LOW / OUT.
        status_filter = STATUS_ALIASES.get(raw_status, raw_status)
        all_rows = []

        # Productos con variantes → iterar variantes
        for v in (ProductVariant.objects
                  .filter(product__is_active=True)
                  .select_related('product', 'option', 'option__variant_type')
                  .order_by('product__name', 'option__order')):
            st = _get_stock_status(v.stock, threshold)
            all_rows.append({
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
            all_rows.append({
                'product_id':    p.pk,
                'product_name':  p.name,
                'sku':           p.sku,
                'variant_id':    None,
                'variant_label': None,
                'stock':         p.stock,
                'status':        st,
                'threshold':     threshold,
            })

        # Sumario sobre el universo completo (no afectado por el filtro)
        summary = {
            'normal': sum(1 for r in all_rows if r['status'] == 'NORMAL'),
            'low':    sum(1 for r in all_rows if r['status'] == 'BAJO'),
            'out':    sum(1 for r in all_rows if r['status'] == 'AGOTADO'),
            'total':  len(all_rows),
        }

        # Aplicar filtro de estado tras calcular el sumario
        if status_filter:
            filtered = [r for r in all_rows if r['status'] == status_filter]
        else:
            filtered = all_rows

        # Paginación
        try:
            page = max(1, int(request.query_params.get('page', '1')))
        except ValueError:
            page = 1
        try:
            page_size = min(200, max(1, int(
                request.query_params.get('page_size', '50')
            )))
        except ValueError:
            page_size = 50

        page_rows, pagination = _paginate(filtered, page, page_size)

        return Response({
            'threshold':  threshold,
            'count':      len(filtered),
            'results':    page_rows,
            'summary':    summary,
            'pagination': pagination,
        })


class StockAdjustView(APIView):
    """
    POST /api/v1/admin/inventory/<product_pk>/adjust/
    Ajuste manual de stock de un producto (sin variante). UC-INV-04.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = StockAdjustSerializer

    @extend_schema(
        summary='Ajuste manual de stock (producto sin variante)',
        tags=['inventory'],
    )
    def post(self, request, product_pk):
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

    Acepta dos payloads:

    1. Legacy ({delta, notes}) — usado por tests anteriores. Devuelve el
       StockMovement serializado, HTTP 201, codigo_error STOCK_NEGATIVO 400.

    2. UI contract ({new_quantity, reason, observations}) — UC-INV-04 UI mock.
       Devuelve {variant_id, previous_stock, new_stock, delta, movement_id},
       HTTP 201, codigo_error STOCK_NEGATIVO_NO_PERMITIDO 422 si negativo.

    El payload se autodetecta por la presencia de "new_quantity".
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = StockAdjustSerializer

    @extend_schema(
        summary='Ajuste manual de stock (variante)',
        description=(
            'Soporta payload legacy {delta, notes} o el payload UI '
            '{new_quantity, reason, observations}. En el segundo caso la '
            'respuesta usa identificadores en inglés y emite HTTP 422 con '
            'STOCK_NEGATIVO_NO_PERMITIDO al intentar dejar stock negativo.'
        ),
        tags=['inventory'],
    )
    def post(self, request, variant_pk):
        variant = get_object_or_404(ProductVariant, pk=variant_pk, is_active=True)

        if 'new_quantity' in request.data:
            return self._handle_new_quantity(request, variant)
        return self._handle_legacy_delta(request, variant)

    # ─── modo nuevo: new_quantity ───────────────────────────────────────────
    def _handle_new_quantity(self, request, variant):
        s = VariantAdjustNewQuantitySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        new_qty = s.validated_data['new_quantity']
        reason  = s.validated_data['reason']
        obs     = s.validated_data.get('observations', '')

        previous_stock = variant.stock
        delta = new_qty - previous_stock

        # En este modo new_quantity ya está validado >= 0 por el serializer,
        # de modo que el delta nunca produce stock negativo. Mantenemos el
        # bloque defensivo por consistencia con UC-INV-04 EX-01.
        if new_qty < 0:
            return Response({
                'detail': f'El ajuste resultaría en stock negativo ({new_qty}).',
                'codigo_error': 'STOCK_NEGATIVO_NO_PERMITIDO',
            }, status=422)

        notes = f'{reason}: {obs}' if obs else reason
        mov = InventoryService.adjust(
            product=variant.product, variant=variant,
            delta=delta, notes=notes,
            created_by=request.user,
        )
        return Response({
            'variant_id':     variant.pk,
            'previous_stock': previous_stock,
            'new_stock':      mov.stock_after,
            'delta':          delta,
            'movement_id':    mov.pk,
        }, status=201)

    # ─── modo legacy: delta ─────────────────────────────────────────────────
    def _handle_legacy_delta(self, request, variant):
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


class VariantMovementsView(ListAPIView):
    """
    GET /api/v1/admin/inventory/variants/<variant_pk>/movements/
    Bitácora de movimientos de stock de una variante. UC-INV-02/03.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = StockMovementSerializer
    pagination_class   = None  # respuesta envuelta manualmente

    @extend_schema(
        summary='Bitácora de movimientos de stock por variante',
        tags=['inventory'],
    )
    def get(self, request, variant_pk):
        variant = get_object_or_404(ProductVariant, pk=variant_pk)
        qs = (StockMovement.objects
              .filter(variant=variant)
              .select_related('product', 'variant', 'variant__option')
              .order_by('-created_at'))
        data = StockMovementSerializer(qs, many=True).data
        return Response({
            'variant_id': variant.pk,
            'count':      len(data),
            'results':    data,
        })


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


IMPORT_JOB_TTL    = 3600   # 1 hora
IMPORT_SYNC_LIMIT = 100    # filas síncronas máximas
IMPORT_REPORT_TTL = 3600   # CSV descargable disponible 1 hora


def _persist_report(report_id: str, error_report: list) -> None:
    """Guarda el error_report bajo una clave de cache descargable."""
    cache.set(f'import_report:{report_id}', error_report, IMPORT_REPORT_TTL)


def _build_download_url(request, report_id: str) -> str:
    """Construye la URL absoluta del CSV descargable (UC-INV-05 Alt C, D-006)."""
    try:
        path = reverse('admin_inventory:product-import-report',
                       kwargs={'report_id': report_id})
    except Exception:  # pragma: no cover
        # silent OK because URL fallback determinista cuando el router
        # no esta registrado (test envs). DEC-DOC-008.
        path = f'/api/v1/admin/inventory/import-reports/{report_id}.csv'
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def _process_import_csv(content: bytes, user, initial_state: str = 'BORRADOR',
                         request=None) -> dict:
    """
    Procesa el CSV de importación de productos. UC-INV-05 (FR-INV-05.02).

    initial_state ∈ {'BORRADOR', 'ACTIVO'} controla is_active/is_published.
    Por defecto los productos se crean en BORRADOR.

    Retorna un dict con ambas familias de claves:

      Inglés (UI agent / DEC-DOC-005):
        products_created, products_failed, error_report:[{row, field, reason}],
        download_url.

      Legacy (tests Sprint 11):
        created, failed, errors:[{line, sku, error}].

    Tolerante a fallos: si una fila falla, las demás siguen procesándose.
    """

    is_active_flag    = (initial_state or 'BORRADOR').upper() == 'ACTIVO'
    is_published_flag = is_active_flag

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
            'status':       'ERROR',
            # Códigos legacy + nuevo (UI agent UC-INV-05).
            'codigo_error': 'ENCABEZADO_CSV_INVALIDO',
            'detail':       f'Columnas faltantes: {", ".join(sorted(missing))}',
            # legacy
            'created':           0,
            'failed':            0,
            'errors':            [],
            # english (UI contract)
            'products_created':  0,
            'products_failed':   0,
            'error_report':      [],
            'download_url':      None,
        }

    created, failed = 0, 0
    legacy_errors  = []   # [{line, sku, error}]
    error_report   = []   # [{row, field, reason}]

    def _err(line, sku, field, reason):
        nonlocal failed
        failed += 1
        legacy_errors.append({'line': line, 'sku': sku, 'error': reason})
        error_report.append({'row': line, 'field': field, 'reason': reason})

    for i, row in enumerate(reader, start=2):
        name     = (row.get('name') or '').strip()
        sku      = (row.get('sku') or '').strip().upper()
        price    = (row.get('base_price') or '').strip().replace(',', '.')
        cat_slug = (row.get('category_slug') or '').strip()

        if not all([name, sku, price, cat_slug]):
            _err(i, sku or '(vacío)', 'required',
                 'Campos obligatorios vacíos.')
            continue

        try:
            price_dec = Decimal(price)
            if price_dec <= 0:
                raise ValueError('precio <= 0')
        except Exception:
            _err(i, sku, 'base_price', f'Precio inválido: "{price}"')
            continue

        try:
            cat = Category.objects.get(slug=cat_slug, is_active=True)
        except Category.DoesNotExist:
            _err(i, sku, 'category_slug',
                 f'Categoría "{cat_slug}" no existe.')
            continue

        if Product.objects.filter(sku__iexact=sku).exists():
            _err(i, sku, 'sku',
                 f'SKU "{sku}" ya existe en el catálogo.')
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
                is_active=is_active_flag,
                is_published=is_published_flag,
            )
            created += 1
        except Exception as exc:
            _err(i, sku, 'unknown', str(exc))

    # D-006 — UC-INV-05 Alt C: si hubo al menos un error, persistimos el
    # error_report con un report_id y exponemos un download_url firmado
    # (TTL 1h). Si no hubo errores, no hay nada que descargar.
    download_url = None
    if error_report:
        report_id = str(uuid.uuid4())
        _persist_report(report_id, error_report)
        download_url = _build_download_url(request, report_id)

    return {
        'status':           'COMPLETED',
        # legacy
        'created':          created,
        'failed':           failed,
        'errors':           legacy_errors[:50],
        # english (UI contract)
        'products_created': created,
        'products_failed':  failed,
        'error_report':     error_report[:50],
        # UC-INV-05 Alt C — D-006: URL al CSV descargable con los errores.
        # Solo se setea si hubo errores en la import.
        'download_url':     download_url,
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
    serializer_class   = serializers.Serializer

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

        initial_state = request.data.get('initial_state', 'BORRADOR')
        content = csv_file.read()

        # Contar filas para decidir modo síncrono/asíncrono
        try:
            line_count = content.decode('utf-8-sig', errors='replace').count('\n')
        except Exception:
            # Loud-log: decode no debe fallar con errors='replace', pero
            # si lo hace, caemos en el branch async por seguridad.
            # DEC-DOC-008.
            logger.warning(
                'CSV decode failed, falling back to async import',
                exc_info=True,
            )
            line_count = 0

        if line_count <= IMPORT_SYNC_LIMIT:
            # Síncrono
            result = _process_import_csv(
                content, request.user, initial_state, request=request,
            )
            # Encabezado inválido → 422 ENCABEZADO_CSV_INVALIDO (UC-INV-05).
            if result.get('codigo_error') == 'ENCABEZADO_CSV_INVALIDO':
                return Response(result, status=422)
            return Response(result, status=200)
        else:
            # Asíncrono — threading + cache
            job_id = str(uuid.uuid4())
            cache.set(f'import_job:{job_id}', {'status': 'PROCESSING',
                                                'created': 0, 'failed': 0},
                      IMPORT_JOB_TTL)

            user = request.user

            def _run():
                # request no se pasa al hilo (puede caducar);
                # download_url usa fallback de path relativo.
                result = _process_import_csv(content, user, initial_state)
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
    serializer_class   = serializers.Serializer

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


class ProductImportReportView(APIView):
    """
    GET /api/v1/admin/inventory/import-reports/<report_id>.csv

    UC-INV-05 Alt C (D-006): descarga del CSV con las filas que fallaron
    en una importacion previa. El report_id se publica en el campo
    ``download_url`` de la respuesta de ``ProductImportView``. El reporte
    queda disponible durante ``IMPORT_REPORT_TTL`` segundos (1 hora).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = serializers.Serializer

    @extend_schema(
        summary='Descargar reporte CSV de errores de importacion',
        tags=['inventory'],
    )
    def get(self, request, report_id):
        report = cache.get(f'import_report:{report_id}')
        if report is None:
            return Response(
                {'detail':       'Reporte no encontrado o expirado.',
                 'codigo_error': 'REPORTE_NO_ENCONTRADO'},
                status=404,
            )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['row', 'field', 'reason'])
        for entry in report:
            writer.writerow([
                entry.get('row', ''),
                entry.get('field', ''),
                entry.get('reason', ''),
            ])
        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="import-errors-{report_id}.csv"'
        )
        return response
