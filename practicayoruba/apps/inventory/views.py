"""
Views — apps.inventory (P-06 / UC-INV-01..05).
"""
import csv
import io
import logging
import math

from django.db import transaction
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalogue.models import Category, Product
from apps.chartsize.models import ProductVariant
from apps.settings_app.models import SiteSettings
from .models import ImportJob, StockAlert, StockMovement
from .serializers import (
    StockMovementSerializer, StockAlertSerializer, StockAdjustSerializer,
    VariantAdjustNewQuantitySerializer,
)
from .services import InventoryService, _get_stock_status

logger = logging.getLogger('apps')


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


def _build_dashboard_items(status_filter=None):
    threshold = SiteSettings.get_current().min_stock_threshold
    items = []
    for p in Product.objects.prefetch_related('variants__option').all():
        variants = list(p.variants.all())
        if variants:
            for v in variants:
                st = _get_stock_status(v.stock, threshold)
                if status_filter and st != status_filter:
                    continue
                items.append({
                    'product_id': p.id, 'product_name': p.name, 'sku': p.sku,
                    'variant_id': v.id, 'variant_label': v.option.label if v.option else None,
                    'stock': v.stock, 'status': st, 'threshold': threshold,
                })
        else:
            st = _get_stock_status(p.stock, threshold)
            if status_filter and st != status_filter:
                continue
            items.append({
                'product_id': p.id, 'product_name': p.name, 'sku': p.sku,
                'variant_id': None, 'variant_label': None,
                'stock': p.stock, 'status': st, 'threshold': threshold,
            })
    return items, threshold


class InventoryDashboardView(_AdminOnly, APIView):
    @extend_schema(summary='Dashboard de inventario (UC-INV-01)', tags=['inventory'], responses={200: None})
    def get(self, request):
        STATUS_ALIAS = {'LOW': 'BAJO', 'OUT': 'AGOTADO'}
        status_filter_raw = request.query_params.get('status')
        status_filter = STATUS_ALIAS.get(status_filter_raw, status_filter_raw) if status_filter_raw else None

        items, threshold = _build_dashboard_items(status_filter)
        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = max(1, min(200, int(request.query_params.get('page_size', 50))))
        except (ValueError, TypeError):
            raise ValidationError({'detail': 'page y page_size deben ser enteros validos.'})
        total     = len(items)
        total_pages = max(1, math.ceil(total / page_size)) if total else 1
        page_items = items[(page - 1) * page_size: page * page_size]

        all_items, _ = _build_dashboard_items(None)
        summary = {
            'normal': sum(1 for r in all_items if r['status'] == 'NORMAL'),
            'low':    sum(1 for r in all_items if r['status'] == 'BAJO'),
            'out':    sum(1 for r in all_items if r['status'] == 'AGOTADO'),
            'total':  len(all_items),
        }
        return Response({
            'results': page_items, 'summary': summary,
            'pagination': {'page': page, 'page_size': page_size, 'total_pages': total_pages, 'total': total},
        })


class StockAdjustView(_AdminOnly, APIView):
    @extend_schema(summary='Ajuste manual de stock de producto (UC-INV-04)', request=StockAdjustSerializer,
                   tags=['inventory'], responses={201: None, 400: None, 404: None})
    @transaction.atomic
    def post(self, request, product_pk):
        try:
            product = Product.objects.select_for_update().get(pk=product_pk)
        except Product.DoesNotExist:
            raise NotFound({'detail': 'Producto no encontrado.', 'codigo_error': 'PRODUCT_NOT_FOUND'})
        ser = StockAdjustSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        data = ser.validated_data
        delta = data['delta']
        new_stock = product.stock + delta
        if new_stock < 0:
            return Response({'detail': 'El ajuste resultaría en stock negativo.', 'codigo_error': 'STOCK_NEGATIVO'}, status=400)
        stock_before = product.stock
        product.stock = new_stock
        product.save(update_fields=['stock', 'updated_at'])
        mov = StockMovement.objects.create(
            product=product, variant=None, delta=delta,
            stock_before=stock_before, stock_after=new_stock,
            movement_type=StockMovement.TYPE_ADJUSTMENT,
            notes=data.get('notes', ''), reason=data.get('reason', ''),
            reference=f'ADMIN:{request.user.pk}', created_by=request.user,
        )
        return Response({'detail': 'Stock ajustado.', 'new_stock': new_stock, 'stock_before': stock_before,
                         'delta': delta, 'reason': mov.reason, 'movement_id': mov.pk}, status=201)


class VariantStockAdjustView(_AdminOnly, APIView):
    @extend_schema(summary='Ajuste manual de stock de variante (UC-INV-04)', tags=['inventory'],
                   responses={201: None, 400: None, 422: None, 404: None})
    @transaction.atomic
    def post(self, request, variant_pk):
        try:
            variant = ProductVariant.objects.select_related('product', 'option').select_for_update().get(pk=variant_pk)
        except ProductVariant.DoesNotExist:
            raise NotFound({'detail': 'Variante no encontrada.', 'codigo_error': 'VARIANT_NOT_FOUND'})
        product = variant.product
        data = request.data

        if 'new_quantity' in data:
            ser = VariantAdjustNewQuantitySerializer(data=data)
            if not ser.is_valid():
                return Response(ser.errors, status=400)
            vdata = ser.validated_data
            new_quantity = vdata['new_quantity']
            if new_quantity < 0:
                return Response({'detail': 'El stock no puede ser negativo.',
                                 'codigo_error': 'NEGATIVE_STOCK_NOT_ALLOWED'}, status=422)
            stock_before = variant.stock
            delta = new_quantity - stock_before
            variant.stock = new_quantity
            variant.save(update_fields=['stock', 'updated_at'])
            notes_text = f"{vdata['reason']}: {vdata.get('observations', '')}" if vdata.get('observations') else vdata['reason']
            mov = StockMovement.objects.create(
                product=product, variant=variant, delta=delta,
                stock_before=stock_before, stock_after=new_quantity,
                movement_type=StockMovement.TYPE_ADJUSTMENT,
                reason=vdata['reason'], notes=notes_text,
                reference=f'ADMIN:{request.user.pk}', created_by=request.user,
            )
            return Response({'variant_id': variant.pk, 'previous_stock': stock_before,
                             'new_stock': new_quantity, 'delta': delta, 'movement_id': mov.pk}, status=201)
        else:
            ser = StockAdjustSerializer(data=data)
            if not ser.is_valid():
                return Response(ser.errors, status=400)
            vdata = ser.validated_data
            delta = vdata['delta']
            new_stock = variant.stock + delta
            if new_stock < 0:
                return Response({'detail': 'El ajuste resultaría en stock negativo.', 'codigo_error': 'STOCK_NEGATIVO'}, status=400)
            stock_before = variant.stock
            variant.stock = new_stock
            variant.save(update_fields=['stock', 'updated_at'])
            mov = StockMovement.objects.create(
                product=product, variant=variant, delta=delta,
                stock_before=stock_before, stock_after=new_stock,
                movement_type=StockMovement.TYPE_ADJUSTMENT,
                notes=vdata.get('notes', ''), reason=vdata.get('reason', ''),
                reference=f'ADMIN:{request.user.pk}', created_by=request.user,
            )
            return Response({'detail': 'Stock ajustado.', 'new_stock': new_stock,
                             'stock_before': stock_before, 'delta': delta,
                             'reason': mov.reason, 'movement_id': mov.pk}, status=201)


class VariantMovementsView(_AdminOnly, APIView):
    @extend_schema(summary='Historial de movimientos de stock (UC-INV-03)', tags=['inventory'],
                   responses={200: StockMovementSerializer(many=True)})
    def get(self, request, variant_pk):
        try:
            variant = ProductVariant.objects.get(pk=variant_pk)
        except ProductVariant.DoesNotExist:
            raise NotFound({'detail': 'Variante no encontrada.', 'codigo_error': 'VARIANT_NOT_FOUND'})
        movements = StockMovement.objects.filter(variant=variant).select_related('product', 'variant__option').order_by('-created_at')
        results = [{'id': m.pk, 'delta': m.delta, 'stock_after': m.stock_after, 'stock_before': m.stock_before,
                    'movement_type': m.movement_type, 'reason': m.reason, 'notes': m.notes, 'created_at': m.created_at}
                   for m in movements]
        return Response({'results': results})


class StockAlertListView(_AdminOnly, APIView):
    @extend_schema(summary='Alertas de stock bajo (UC-INV-02)', tags=['inventory'],
                   responses={200: StockAlertSerializer(many=True)})
    def get(self, request):
        alerts = StockAlert.objects.filter(resolved=False).select_related('variant__option', 'product').order_by('-created_at')
        return Response(StockAlertSerializer(alerts, many=True).data)


def _process_import_csv(file_obj, initial_state: str, admin_user) -> dict:
    REQUIRED_HEADERS = {'name', 'sku', 'base_price', 'category_slug'}
    try:
        content = file_obj.read()
        reader = csv.DictReader(io.TextIOWrapper(io.BytesIO(content), encoding='utf-8'))
        headers = set(reader.fieldnames or [])
    except Exception:
        raise ValidationError({'detail': 'No se pudo leer el archivo CSV.', 'codigo_error': 'CSV_READ_ERROR'})

    if not REQUIRED_HEADERS <= headers:
        missing = REQUIRED_HEADERS - headers
        return None, {'status_code': 422, 'detail': f'Encabezados inválidos. Faltan: {missing}', 'codigo_error': 'CSV_HEADER_INVALID'}

    is_active = is_published = (initial_state == 'ACTIVO')
    rows = list(reader)
    created = failed = 0
    error_report = []

    for i, row in enumerate(rows, start=2):
        try:
            sku = row.get('sku', '').strip()
            name = row.get('name', '').strip()
            base_price = row.get('base_price', '').strip()
            category_slug = row.get('category_slug', '').strip()
            if not sku:
                raise ValueError('SKU vacío')
            from decimal import Decimal, InvalidOperation
            try:
                price = Decimal(base_price)
            except (InvalidOperation, ValueError):
                raise ValueError(f'Precio inválido: {base_price!r}')
            try:
                category = Category.objects.get(slug=category_slug)
            except Category.DoesNotExist:
                raise ValueError(f'Categoría no encontrada: {category_slug!r}')
            if Product.objects.filter(sku=sku).exists():
                raise ValueError(f'SKU duplicado: {sku!r}')
            Product.objects.create(
                name=name, slug=sku.lower().replace(' ', '-'), sku=sku,
                description='', price=price, category=category,
                is_active=is_active, is_published=is_published,
            )
            created += 1
        except Exception as exc:
            failed += 1
            error_report.append({'row': i, 'field': _guess_error_field(exc), 'reason': str(exc)})

    return {'created': created, 'failed': failed, 'products_created': created,
            'products_failed': failed, 'error_report': error_report}, None


def _guess_error_field(exc) -> str:
    msg = str(exc).lower()
    for kw, field in [('sku', 'sku'), ('precio', 'base_price'), ('price', 'base_price'),
                      ('categor', 'category_slug'), ('category_slug', 'category_slug'), ('name', 'name')]:
        if kw in msg:
            return field
    return 'unknown'


_CSV_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB — UC-INV-05


class ProductImportView(_AdminOnly, APIView):
    @extend_schema(summary='Importar productos desde CSV (UC-INV-05)', tags=['inventory'],
                   responses={200: None, 400: None, 422: None})
    def post(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'detail': 'El archivo CSV es requerido.', 'codigo_error': 'FILE_REQUIRED'}, status=400)
        # H-CICLO26-05: validar extensión y content-type del archivo subido.
        # Sin esta comprobación un atacante podría subir un archivo arbitrario
        # (HTML, ejecutable, etc.) que se almacenará en MEDIA_ROOT con el
        # nombre original. La extensión no es garantía suficiente, pero junto
        # con el content-type declarado por el cliente reduce el riesgo.
        _allowed_content_types = {
            'text/csv', 'text/plain', 'application/csv',
            'application/vnd.ms-excel',
        }
        file_name = csv_file.name or ''
        if not file_name.lower().endswith('.csv'):
            return Response(
                {'detail': 'Solo se admiten archivos .csv.', 'codigo_error': 'FILE_TYPE_INVALID'},
                status=400,
            )
        if csv_file.content_type and csv_file.content_type.split(';')[0].strip() not in _allowed_content_types:
            return Response(
                {'detail': 'Tipo de contenido no permitido. Use text/csv.', 'codigo_error': 'FILE_TYPE_INVALID'},
                status=400,
            )
        # H-CICLO23-07: limitar tamaño del CSV para evitar que un archivo
        # masivo agote memoria del worker WSGI o consuma demasiado tiempo.
        if csv_file.size > _CSV_MAX_SIZE_BYTES:
            return Response(
                {
                    'detail': (
                        f'El archivo supera el límite de '
                        f'{_CSV_MAX_SIZE_BYTES // (1024 * 1024)} MB.'
                    ),
                    'codigo_error': 'FILE_TOO_LARGE',
                },
                status=400,
            )
        result, error = _process_import_csv(csv_file, request.data.get('initial_state', 'BORRADOR'), request.user)
        if error:
            return Response({'detail': error['detail'], 'codigo_error': error['codigo_error']}, status=error['status_code'])

        # H-INV-RPT: Persistir el reporte de errores en la BD (ImportJob.errors)
        # para que sea accesible entre procesos WSGI y no se pierda al reiniciar.
        # El dict de módulo _IMPORT_ERROR_REPORTS era volátil: en producción con
        # múltiples workers/procesos, el reporte se perdía inmediatamente.
        download_url = None
        if result['error_report']:
            job = ImportJob.objects.create(
                uploaded_by=request.user,
                file=csv_file,
                status=ImportJob.STATUS_DONE,
                total_rows=result['created'] + result['failed'],
                imported_rows=result['created'],
                failed_rows=result['failed'],
                errors=result['error_report'],
            )
            download_url = request.build_absolute_uri(
                f'/api/v1/admin/inventory/import-reports/{job.pk}.csv'
            )
        result['download_url'] = download_url
        return Response(result, status=200)


class ProductImportStatusView(_AdminOnly, APIView):
    @extend_schema(summary='Estado de importación (UC-INV-05)', tags=['inventory'], responses={200: None, 404: None})
    def get(self, request, job_id):
        try:
            job = ImportJob.objects.get(pk=int(job_id))
        except (ImportJob.DoesNotExist, ValueError, TypeError):
            raise NotFound({'detail': 'Job no encontrado.', 'codigo_error': 'JOB_NOT_FOUND'})
        return Response({'id': job.id, 'status': job.status, 'total_rows': job.total_rows,
                         'imported_rows': job.imported_rows, 'failed_rows': job.failed_rows, 'created_at': job.created_at})


class ProductImportReportView(_AdminOnly, APIView):
    @extend_schema(summary='Descarga CSV de errores de importación', tags=['inventory'], responses={200: None, 404: None})
    def get(self, request, report_id):
        # H-INV-RPT: Leer el reporte de errores desde la BD (ImportJob.errors)
        # en lugar del dict de módulo efímero que se perdía entre workers WSGI.
        try:
            job = ImportJob.objects.get(pk=int(report_id))
        except (ImportJob.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Reporte no encontrado.', 'codigo_error': 'REPORT_NOT_FOUND'}, status=404)
        rows = job.errors or []
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=['row', 'field', 'reason'])
        writer.writeheader()
        writer.writerows(rows)
        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="import-errors-{report_id}.csv"'
        return response
