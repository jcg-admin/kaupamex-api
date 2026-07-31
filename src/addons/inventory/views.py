"""
Views — addons.inventory (P-06 / UC-INV-01..05).
"""
import csv
import io
import logging
import math
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from addons.authz.permissions import HasCapability
from addons.authz.services import is_superadmin
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.catalogue.models import Category, Product
from addons.chartsize.models import ProductVariant
from addons.sale.status_projection import order_status
from addons.sale.models import SaleOrder
from addons.payment.models import Payment
from addons.base.models import SiteSettings
from addons.users.models import BusinessEvent
from .models import ImportJob, StockAlert, StockMovement
from .serializers import (
    StockMovementSerializer, StockAlertSerializer, StockAdjustSerializer,
    VariantAdjustNewQuantitySerializer, RestockSerializer,
)
from .services import InventoryService, _get_stock_status
from config.schema import error_response

logger = logging.getLogger('apps')


class _AdminOnly:
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'inventory.edit'


class StockAlertPagination(PageNumberPagination):
    """H-CICLO80-03: paginar alertas para evitar respuesta sin limite."""
    page_size             = 50
    page_size_query_param = 'page_size'
    max_page_size         = 200


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

        all_items, threshold = _build_dashboard_items(None)
        summary = {
            'normal': sum(1 for r in all_items if r['status'] == 'NORMAL'),
            'low':    sum(1 for r in all_items if r['status'] == 'BAJO'),
            'out':    sum(1 for r in all_items if r['status'] == 'AGOTADO'),
            'total':  len(all_items),
        }
        items = [r for r in all_items if not status_filter or r['status'] == status_filter]
        try:
            page      = max(1, int(request.query_params.get('page', 1)))
            page_size = max(1, min(200, int(request.query_params.get('page_size', 50))))
        except (ValueError, TypeError):
            raise ValidationError({'detail': 'page y page_size deben ser enteros validos.'})
        total     = len(items)
        total_pages = max(1, math.ceil(total / page_size)) if total else 1
        page_items = items[(page - 1) * page_size: page * page_size]
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
                   request=VariantAdjustNewQuantitySerializer,
                   responses={201: inline_serializer(
                       'VariantStockAdjustResponse',
                       {'detail': serializers.CharField(),
                        'new_stock': serializers.IntegerField(),
                        'stock_before': serializers.IntegerField(),
                        'delta': serializers.IntegerField(),
                        'reason': serializers.CharField(),
                        'movement_id': serializers.IntegerField()}),
                       400: error_response('Datos inválidos'),
                       404: error_response('Variante no encontrada'),
                       422: error_response('Stock negativo no permitido')})
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
            if new_quantity == 0:
                # AC-06 / RNF-AUDIT-001: capture at-risk orders in the same
                # transaction so the audit record reflects the exact state
                # at the moment stock was zeroed (ADR-011 round 2).
                # Cut-over orders→sale (ADR-024): "at-risk" = confirmed sale
                # order (state='sale') WITHOUT an approved payment. The
                # fulfillment axis is not needed — shipping implies payment.
                at_risk_items = (
                    SaleOrderLine.objects
                    .filter(
                        variant_id=variant.pk,
                        order__sale_order__state=SaleOrder.STATE_SALE,
                    )
                    .exclude(
                        order__sale_order__payments__status=Payment.STATUS_APPROVED,
                    )
                    .select_related('order__sale_order')
                )
                at_risk = [
                    {
                        'order_id':     item.order_id,
                        'order_number': item.order.order_number,
                        'status':       order_status(item.order),
                        'quantity':     item.quantity,
                    }
                    for item in at_risk_items
                ]
                BusinessEvent.objects.create(
                    actor=request.user,
                    action=BusinessEvent.ACTION_STOCK_ADJUSTED_TO_ZERO,
                    target_type=BusinessEvent.TARGET_VARIANT,
                    target_id=variant.pk,
                    ip_addr=request.META.get('REMOTE_ADDR'),
                    extra_json={
                        'variant_id':    variant.pk,
                        'product_id':    product.pk,
                        'stock_before':  stock_before,
                        'movement_id':   mov.pk,
                        'orders_at_risk': at_risk,
                    },
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


class VariantRestockView(_AdminOnly, APIView):
    """
    POST /api/v1/admin/inventory/variants/<variant_pk>/restock/

    Entrada de stock (reabastecimiento). UC-INV. A diferencia del ajuste
    manual (UC-INV-04), restock siempre es una entrada positiva ligada a una
    referencia de compra y registra un StockMovement de tipo RESTOCK.
    """
    @extend_schema(
        summary='Entrada de stock de variante (UC-INV)',
        tags=['inventory'],
        request=RestockSerializer,
        responses={201: inline_serializer(
            'VariantRestockResponse',
            {'detail': serializers.CharField(),
             'variant_id': serializers.IntegerField(),
             'stock_before': serializers.IntegerField(),
             'new_stock': serializers.IntegerField(),
             'delta': serializers.IntegerField(),
             'reference': serializers.CharField(),
             'movement_id': serializers.IntegerField()}),
            400: error_response('Cantidad inválida'),
            404: error_response('Variante no encontrada')})
    def post(self, request, variant_pk):
        ser = RestockSerializer(data=request.data)
        if not ser.is_valid():
            return Response(
                {'detail': 'La cantidad de entrada debe ser un entero positivo.',
                 'codigo_error': 'INVALID_QUANTITY'},
                status=400,
            )
        data = ser.validated_data
        try:
            variant = ProductVariant.objects.select_related('product', 'option').get(pk=variant_pk)
        except ProductVariant.DoesNotExist:
            raise NotFound({'detail': 'Variante no encontrada.', 'codigo_error': 'VARIANT_NOT_FOUND'})

        mov = InventoryService.restock(
            product=variant.product, variant=variant,
            quantity=data['quantity'], reference=data.get('reference', ''),
            notes=data.get('notes', ''), created_by=request.user,
        )
        return Response({
            'detail': 'Entrada de stock registrada.',
            'variant_id': variant.pk,
            'stock_before': mov.stock_before,
            'new_stock': mov.stock_after,
            'delta': mov.delta,
            'reference': mov.reference,
            'movement_id': mov.pk,
        }, status=201)


class ZeroStockCheckView(_AdminOnly, APIView):
    """
    Round 1 del guard two-round (ADR-011 / UC-INV-04 EX-02).
    Detecta órdenes en riesgo que referencian esta variante — las únicas
    cuyo decremento futuro fallaría si stock llega a 0.

    Cut-over orders→sale (ADR-024): "en riesgo" = orden confirmada
    (``sale.state='sale'``) SIN pago aprobado. El eje de fulfillment no
    se necesita porque enviar implica pagar.
    COSMIC: 1E + 1R(variant) + 1R(SaleOrderLine) + 1X = 4 CFP.
    """
    @extend_schema(
        summary='Guard check: órdenes en riesgo al ajustar variante a cero (UC-INV-04 EX-02 Round 1)',
        tags=['inventory'],
        responses={200: None, 404: None},
    )
    def get(self, request, variant_pk):
        try:
            variant = ProductVariant.objects.get(pk=variant_pk)
        except ProductVariant.DoesNotExist:
            raise NotFound({'detail': 'Variante no encontrada.', 'codigo_error': 'VARIANT_NOT_FOUND'})

        risk_items = (
            SaleOrderLine.objects
            .filter(
                variant_id=variant.pk,
                order__sale_order__state=SaleOrder.STATE_SALE,
            )
            .exclude(
                order__sale_order__payments__status=Payment.STATUS_APPROVED,
            )
            .select_related('order__sale_order')
        )
        active_orders = [
            {
                'order_id':     item.order_id,
                'order_number': item.order.order_number,
                'status':       order_status(item.order),
                'quantity':     item.quantity,
            }
            for item in risk_items
        ]
        return Response({
            'active_orders':          active_orders,
            'requires_confirmation':  bool(active_orders),
        })


class VariantMovementsPagination(PageNumberPagination):
    """H-CICLO83-01: paginar movimientos de variante para evitar respuesta sin limite."""
    page_size             = 50
    page_size_query_param = 'page_size'
    max_page_size         = 200


class VariantMovementsView(_AdminOnly, APIView):
    @extend_schema(summary='Historial de movimientos de stock (UC-INV-03)', tags=['inventory'],
                   responses={200: StockMovementSerializer(many=True)})
    def get(self, request, variant_pk):
        try:
            variant = ProductVariant.objects.get(pk=variant_pk)
        except ProductVariant.DoesNotExist:
            raise NotFound({'detail': 'Variante no encontrada.', 'codigo_error': 'VARIANT_NOT_FOUND'})
        movements = (
            StockMovement.objects
            .filter(variant=variant)
            .select_related('product', 'variant__option')
            .order_by('-created_at')
        )
        # H-CICLO83-01: paginar para evitar OOM en variantes con muchos
        # movimientos. Sin paginacion un producto de alta rotacion puede
        # tener miles de filas y la respuesta agota memoria del worker.
        paginator = VariantMovementsPagination()
        page = paginator.paginate_queryset(movements, request)
        if page is not None:
            results = [
                {'id': m.pk, 'delta': m.delta, 'stock_after': m.stock_after,
                 'stock_before': m.stock_before, 'movement_type': m.movement_type,
                 'reason': m.reason, 'notes': m.notes, 'created_at': m.created_at}
                for m in page
            ]
            return paginator.get_paginated_response(results)
        results = [
            {'id': m.pk, 'delta': m.delta, 'stock_after': m.stock_after,
             'stock_before': m.stock_before, 'movement_type': m.movement_type,
             'reason': m.reason, 'notes': m.notes, 'created_at': m.created_at}
            for m in movements
        ]
        return Response({'results': results})


class StockAlertListView(_AdminOnly, APIView):
    @extend_schema(summary='Alertas de stock bajo (UC-INV-02)', tags=['inventory'],
                   responses={200: StockAlertSerializer(many=True)})
    def get(self, request):
        # H-CICLO80-03: paginate stock alerts. Without pagination a warehouse
        # with hundreds of SKUs below threshold returns the full table in one
        # response, wasting memory and bandwidth on every dashboard poll.
        alerts = (
            StockAlert.objects.filter(resolved=False)
            .select_related('variant__option', 'product')
            .order_by('-created_at')
        )
        paginator = StockAlertPagination()
        page = paginator.paginate_queryset(alerts, request)
        if page is not None:
            return paginator.get_paginated_response(
                StockAlertSerializer(page, many=True).data
            )
        return Response(StockAlertSerializer(alerts, many=True).data)


class StockAlertResolveView(_AdminOnly, APIView):
    """
    POST /api/v1/admin/inventory/alerts/<pk>/resolve/
    Marca una alerta de stock como resuelta.
    UC-INV-02 (accion de resolucion manual).

    H-CICLO104-03: select_for_update() + atomic() previene que dos admins
    resuelvan la misma alerta concurrentemente y guarden resolved_at
    diferente. La alerta se registra en StockMovement como pista de
    auditoria (type=TYPE_ADJUSTMENT con notes=ALERT_RESOLVED).
    """
    @extend_schema(
        summary='Resolver alerta de stock (UC-INV-02)',
        tags=['inventory'],
        request=None,
        responses={200: StockAlertSerializer,
                   404: error_response('Alerta no encontrada')},
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            alert = StockAlert.objects.select_for_update().get(pk=pk)
        except StockAlert.DoesNotExist:
            raise NotFound({'detail': 'Alerta no encontrada.', 'codigo_error': 'ALERT_NOT_FOUND'})
        if alert.resolved:
            return Response(StockAlertSerializer(alert).data)
        alert.resolved = True
        alert.resolved_at = timezone.now()
        alert.save(update_fields=['resolved', 'resolved_at'])
        # Audit trail: StockMovement con delta=0 solo para traza — se usa
        # notes para identificar el origen. El delta se deja en 0 para que
        # no altere inventario; la razon CONTEO_FISICO es la mas apropiada
        # segun el enum de ADJUSTMENT_REASONS para una resolucion manual.
        StockMovement.objects.create(
            product=alert.product,
            variant=alert.variant,
            delta=0,
            stock_before=alert.stock_at_alert,
            stock_after=alert.stock_at_alert,
            movement_type=StockMovement.TYPE_ADJUSTMENT,
            reason='PHYSICAL_COUNT',
            notes=f'ALERT_RESOLVED:alert_id={alert.pk}',
            reference=f'ADMIN:{request.user.pk}',
            created_by=request.user,
        )
        return Response(StockAlertSerializer(alert).data)


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

    # Validate all rows first so we can abort the whole import atomically
    # if any row is invalid (H-CICLO72-02: no partial imports).
    to_create = []
    for i, row in enumerate(rows, start=2):
        try:
            sku = row.get('sku', '').strip()
            name = row.get('name', '').strip()
            base_price = row.get('base_price', '').strip()
            category_slug = row.get('category_slug', '').strip()
            if not sku:
                raise ValueError('SKU vacío')
            try:
                price = Decimal(base_price)
                if price.is_nan() or price.is_infinite():
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                raise ValueError(f'Precio inválido: {base_price!r}')
            try:
                category = Category.objects.get(slug=category_slug)
            except Category.DoesNotExist:
                raise ValueError(f'Categoría no encontrada: {category_slug!r}')
            if Product.objects.filter(sku=sku).exists():
                raise ValueError(f'SKU duplicado: {sku!r}')
            to_create.append((i, name, sku, price, category))
            created += 1
        except Exception as exc:
            failed += 1
            error_report.append({'row': i, 'field': _guess_error_field(exc), 'reason': str(exc)})

    # Only persist if every row passed validation — all-or-nothing semantics.
    if not error_report:
        with transaction.atomic():
            for _i, name, sku, price, category in to_create:
                _p = Product.objects.create(
                    name=name, slug=sku.lower().replace(' ', '-'), sku=sku,
                    description='', price=price,
                    is_active=is_active, is_published=is_published,
                )
                _p.categories.add(category)

    return {'created': created if not error_report else 0,
            'failed': failed, 'products_created': created if not error_report else 0,
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
                   request=inline_serializer('ProductImportRequest', {
                       'file': serializers.FileField(),
                   }),
                   responses={200: None,
                              400: error_response('Archivo inválido'),
                              422: error_response('Error de procesamiento del CSV')})
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
                f'/api/v2/admin/inventory/import-reports/{job.pk}.csv'
            )
        result['download_url'] = download_url
        return Response(result, status=200)


class ProductImportStatusView(_AdminOnly, APIView):
    @extend_schema(summary='Estado de importación (UC-INV-05)', tags=['inventory'], responses={200: None, 404: None})
    def get(self, request, job_id):
        try:
            # H-CICLO81-01: filtrar por uploaded_by para evitar IDOR entre
            # admins. Sin el filtro cualquier admin puede consultar el job de
            # otro admin conociendo su PK secuencial. Los superusuarios pueden
            # ver todos los jobs (necesario para soporte y depuracion).
            # Party/authz (T-201): "superusuario" = titular del rol superadmin.
            qs = ImportJob.objects
            if not is_superadmin(request.user):
                qs = qs.filter(uploaded_by=request.user)
            job = qs.get(pk=int(job_id))
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


_VALID_ALERT_ACTIONS = {'resolve'}


class StockAdjustV2View(APIView):
    """
    PATCH /api/v2/admin/inventory/<product_pk>/

    Tier B: POST /adjust/ → PATCH directo sobre el recurso.
    Delega la logica de negocio a StockAdjustView.post().
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'inventory.edit'

    def patch(self, request, product_pk):
        return StockAdjustView().post(request, product_pk)


class VariantStockV2View(APIView):
    """
    PATCH /api/v2/admin/inventory/variants/<variant_pk>/

    Tier B: POST /adjust/ → PATCH sobre la variante.
    Delega a VariantStockAdjustView.post().
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'inventory.edit'

    def patch(self, request, variant_pk):
        return VariantStockAdjustView().post(request, variant_pk)


class VariantRestocksV2View(APIView):
    """
    POST /api/v2/admin/inventory/variants/<variant_pk>/restocks/

    Tier A rename: /restock/ → /restocks/ (plural canonico REST).
    Delega a VariantRestockView.post().
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'inventory.edit'

    def post(self, request, variant_pk):
        return VariantRestockView().post(request, variant_pk)


class StockAlertStatusV2View(APIView):
    """
    PATCH /api/v2/admin/inventory/alerts/<pk>/

    Tier B: POST /alerts/<pk>/resolve/ → PATCH con {action: resolve}.
    Solo la accion 'resolve' esta soportada en esta version.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'inventory.edit'

    def patch(self, request, pk):
        action = request.data.get('action')
        if action not in _VALID_ALERT_ACTIONS:
            return Response(
                {'detail': 'Accion no valida.', 'codigo_error': 'INVALID_ACTION'},
                status=400,
            )
        return StockAlertResolveView().post(request, pk)
