"""
Views — apps.inventory (P-06 / UC-INV-01..05).

Admin:
  GET  /api/v1/admin/inventory/dashboard/        UC-INV-01 resumen stock.
  POST /api/v1/admin/inventory/<id>/adjust/      UC-INV-02 ajuste manual.
  POST /api/v1/admin/inventory/<id>/variants/<vid>/adjust/  UC-INV-02 variante.
  GET  /api/v1/admin/inventory/<id>/variants/<vid>/movements/ UC-INV-03 historial.
  GET  /api/v1/admin/inventory/alerts/           UC-INV-04 alertas de stock bajo.
  POST /api/v1/admin/inventory/import/           UC-INV-05 importar productos CSV.
  GET  /api/v1/admin/inventory/import/<job_id>/status/  UC-INV-05 estado.
  GET  /api/v1/admin/inventory/import/<job_id>/report/  UC-INV-05 reporte.
"""
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from .models import ImportJob, StockAlert, StockMovement
from .serializers import (
    ImportJobSerializer,
    StockAdjustSerializer,
    StockAlertSerializer,
    StockMovementSerializer,
)
from .tasks import run_product_import




class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class InventoryDashboardView(_AdminOnly, APIView):
    """GET /api/v1/admin/inventory/dashboard/ — UC-INV-01."""

    @extend_schema(
        summary='Resumen de stock (UC-INV-01)',
        tags=['inventory'],
        responses={200: None},
    )
    def get(self, request):
        products = Product.objects.filter(is_active=True).prefetch_related('variants')
        data = []
        for p in products:
            variants = p.variants.all()
            total_stock = sum(v.stock for v in variants)
            low_stock   = [v for v in variants if 0 < v.stock <= (v.low_stock_threshold or 5)]
            out_of_stock = [v for v in variants if v.stock == 0]
            data.append({
                'product_id':    p.id,
                'product_name':  p.name,
                'total_stock':   total_stock,
                'variants_count': len(variants),
                'low_stock_count': len(low_stock),
                'out_of_stock_count': len(out_of_stock),
            })
        return Response({'products': data, 'total_products': len(data)})


class StockAdjustView(_AdminOnly, APIView):
    """POST /api/v1/admin/inventory/<id>/adjust/ — UC-INV-02 (producto completo)."""

    @extend_schema(
        summary='Ajuste manual de stock de producto (UC-INV-02)',
        request=StockAdjustSerializer,
        tags=['inventory'],
        responses={200: None, 400: None, 404: None},
    )
    @transaction.atomic
    def post(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise NotFound({'detail': 'Producto no encontrado.',
                            'codigo_error': 'PRODUCT_NOT_FOUND'})

        ser = StockAdjustSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Aplica el ajuste a todas las variantes o solo la especificada
        variants = product.variants.all()
        if not variants.exists():
            raise ValidationError({'detail': 'El producto no tiene variantes.',
                                    'codigo_error': 'NO_VARIANTS'})

        movements = []
        for variant in variants:
            old_stock = variant.stock
            if data['adjustment_type'] == 'absolute':
                variant.stock = data['quantity']
            else:
                variant.stock = max(0, variant.stock + data['quantity'])
            variant.save(update_fields=['stock'])
            movements.append(StockMovement(
                variant=variant,
                quantity_delta=variant.stock - old_stock,
                reason=data.get('reason', ''),
                performed_by=request.user,
            ))
        StockMovement.objects.bulk_create(movements)

        return Response({'detail': f'Stock ajustado para {len(movements)} variante(s).'})


class VariantStockAdjustView(_AdminOnly, APIView):
    """POST /api/v1/admin/inventory/<pid>/variants/<vid>/adjust/ — UC-INV-02."""

    @extend_schema(
        summary='Ajuste manual de stock de variante (UC-INV-02)',
        request=StockAdjustSerializer,
        tags=['inventory'],
        responses={200: None, 400: None, 404: None},
    )
    @transaction.atomic
    def post(self, request, product_id, variant_id):
        try:
            variant = ProductVariant.objects.get(pk=variant_id, product_id=product_id)
        except ProductVariant.DoesNotExist:
            raise NotFound({'detail': 'Variante no encontrada.',
                            'codigo_error': 'VARIANT_NOT_FOUND'})

        ser = StockAdjustSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        old_stock = variant.stock
        if data['adjustment_type'] == 'absolute':
            variant.stock = data['quantity']
        else:
            variant.stock = max(0, variant.stock + data['quantity'])
        variant.save(update_fields=['stock'])

        StockMovement.objects.create(
            variant=variant,
            quantity_delta=variant.stock - old_stock,
            reason=data.get('reason', ''),
            performed_by=request.user,
        )
        return Response({'detail': 'Stock ajustado.', 'new_stock': variant.stock})


class VariantMovementsView(_AdminOnly, APIView):
    """GET /api/v1/admin/inventory/<pid>/variants/<vid>/movements/ — UC-INV-03."""

    @extend_schema(
        summary='Historial de movimientos de stock (UC-INV-03)',
        tags=['inventory'],
        responses={200: StockMovementSerializer(many=True)},
    )
    def get(self, request, product_id, variant_id):
        try:
            variant = ProductVariant.objects.get(pk=variant_id, product_id=product_id)
        except ProductVariant.DoesNotExist:
            raise NotFound({'detail': 'Variante no encontrada.',
                            'codigo_error': 'VARIANT_NOT_FOUND'})
        movements = StockMovement.objects.filter(variant=variant).order_by('-created_at')
        return Response(StockMovementSerializer(movements, many=True).data)


class StockAlertListView(_AdminOnly, APIView):
    """GET /api/v1/admin/inventory/alerts/ — UC-INV-04."""

    @extend_schema(
        summary='Alertas de stock bajo (UC-INV-04)',
        tags=['inventory'],
        responses={200: StockAlertSerializer(many=True)},
    )
    def get(self, request):
        alerts = StockAlert.objects.filter(is_resolved=False).select_related(
            'variant__product'
        ).order_by('-created_at')
        return Response(StockAlertSerializer(alerts, many=True).data)


class ProductImportView(_AdminOnly, APIView):
    """POST /api/v1/admin/inventory/import/ — UC-INV-05."""

    @extend_schema(
        summary='Importar productos desde CSV (UC-INV-05)',
        tags=['inventory'],
        responses={202: ImportJobSerializer, 400: None},
    )
    def post(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            raise ValidationError({'detail': 'El archivo CSV es requerido.',
                                    'codigo_error': 'FILE_REQUIRED'})
        if not csv_file.name.endswith('.csv'):
            raise ValidationError({'detail': 'El archivo debe ser CSV.',
                                    'codigo_error': 'INVALID_FILE_TYPE'})

        job = ImportJob.objects.create(
            uploaded_by=request.user,
            status=ImportJob.STATUS_PENDING,
        )
        job.file.save(csv_file.name, csv_file, save=True)

        # Trigger async task
        run_product_import(job.id)

        return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class ProductImportStatusView(_AdminOnly, APIView):
    """GET /api/v1/admin/inventory/import/<job_id>/status/ — UC-INV-05."""

    @extend_schema(
        summary='Estado de importación de productos (UC-INV-05)',
        tags=['inventory'],
        responses={200: ImportJobSerializer, 404: None},
    )
    def get(self, request, job_id):
        try:
            job = ImportJob.objects.get(pk=job_id)
        except ImportJob.DoesNotExist:
            raise NotFound({'detail': 'Job no encontrado.',
                            'codigo_error': 'JOB_NOT_FOUND'})
        return Response(ImportJobSerializer(job).data)


class ProductImportReportView(_AdminOnly, APIView):
    """GET /api/v1/admin/inventory/import/<job_id>/report/ — UC-INV-05."""

    @extend_schema(
        summary='Reporte de importación de productos (UC-INV-05)',
        tags=['inventory'],
        responses={200: None, 404: None},
    )
    def get(self, request, job_id):
        try:
            job = ImportJob.objects.get(pk=job_id)
        except ImportJob.DoesNotExist:
            raise NotFound({'detail': 'Job no encontrado.',
                            'codigo_error': 'JOB_NOT_FOUND'})
        return Response({
            'job_id': job.id,
            'status': job.status,
            'total_rows': job.total_rows,
            'imported_rows': job.imported_rows,
            'failed_rows': job.failed_rows,
            'errors': job.errors or [],
        })
