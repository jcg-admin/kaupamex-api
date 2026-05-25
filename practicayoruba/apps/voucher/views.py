"""
Views — apps.voucher (Sprint 13)
UC-PRO-01: Crear Voucher
UC-PRO-02: Editar Voucher
UC-PRO-03: Desactivar Voucher
UC-PRO-04: Reporte de Uso
"""
import csv
import io
from decimal import Decimal as PyDecimal
from django.shortcuts import get_object_or_404 as _get404

from django.db import transaction
from django.db.models import (
    Count, DecimalField as DjDecimalField, IntegerField,
    OuterRef, Subquery, Sum,
)
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.generics import ListAPIView
from apps.orders.models import Order
from .models import Voucher, VoucherChangeLog
from .serializers import VoucherSerializer, VoucherReportSerializer



class VoucherViewSet(ModelViewSet):
    """
    GET    /api/v1/admin/vouchers/        — listar  (UC-PRO-04)
    POST   /api/v1/admin/vouchers/        — crear   (UC-PRO-01)
    GET    /api/v1/admin/vouchers/<pk>/   — detalle
    PATCH  /api/v1/admin/vouchers/<pk>/   — editar  (UC-PRO-02)
    DELETE /api/v1/admin/vouchers/<pk>/   — desactivar (UC-PRO-03)
    POST   /api/v1/admin/vouchers/<pk>/activate/ — reactivar
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = VoucherSerializer
    queryset           = Voucher.objects.all().order_by('-created_at')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        VoucherChangeLog.objects.create(
            voucher=instance,
            changed_by=self.request.user,
            changes={'action': 'created', 'code': instance.code},
        )

    def perform_update(self, serializer):
        old = {f: getattr(serializer.instance, f)
               for f in serializer.validated_data}
        instance = serializer.save()
        changes = {}
        for field, new_val in serializer.validated_data.items():
            before = old.get(field)
            if str(before) != str(new_val):
                changes[field] = {'before': str(before), 'after': str(new_val)}
        if changes:
            VoucherChangeLog.objects.create(
                voucher=instance,
                changed_by=self.request.user,
                changes=changes,
            )

    def perform_destroy(self, instance):
        """Soft delete (UC-PRO-03 + DEC-DOC-007)."""
        VoucherChangeLog.objects.create(
            voucher=instance,
            changed_by=self.request.user,
            changes={'action': 'deleted', 'code': instance.code},
        )
        now = timezone.now()
        instance.is_active      = False
        instance.deactivated_at = now
        instance.deactivated_by = self.request.user
        instance.is_deleted     = True
        instance.deleted_at     = now
        instance.save(update_fields=[
            'is_active', 'deactivated_at', 'deactivated_by',
            'is_deleted', 'deleted_at', 'updated_at',
        ])

    @action(detail=True, methods=['post'], url_path='activate')
    @extend_schema(
        summary='Reactivar voucher desactivado',
        responses={200: VoucherSerializer},
        tags=['vouchers'],
    )
    def activate(self, request, pk=None):
        with transaction.atomic():
            voucher = Voucher.all_objects.select_for_update().get(pk=pk)
            if voucher.is_active and not voucher.is_deleted:
                return Response({'detail': 'El voucher ya está activo.'}, status=400)
            voucher.is_active      = True
            voucher.is_deleted      = False
            voucher.deleted_at      = None
            voucher.deactivated_at = None
            voucher.deactivated_by = None
            voucher.save(update_fields=['is_active', 'is_deleted', 'deleted_at', 'deactivated_at', 'deactivated_by', 'updated_at'])
        return Response(VoucherSerializer(voucher).data)

    @action(detail=True, methods=['post'], url_path='deactivate')
    @extend_schema(
        summary='Desactivar voucher (UC-PRO-03)',
        description=(
            'Desactivacion explicita via POST — contrato esperado por el UI. '
            'Equivalente funcional al DELETE soft-delete, expuesto como accion '
            'nombrada para que el UI pueda mostrar confirmacion con '
            '`current_uses` antes de invocar.'
        ),
        responses={200: VoucherSerializer},
        tags=['vouchers'],
    )
    def deactivate(self, request, pk=None):
        voucher = self.get_object()
        if not voucher.is_active:
            return Response(
                {'detail': 'El voucher ya está inactivo.',
                 'codigo_error': 'VOUCHER_ALREADY_INACTIVE'},
                status=400,
            )
        voucher.is_active      = False
        voucher.deactivated_at = timezone.now()
        voucher.deactivated_by = request.user
        voucher.save(update_fields=['is_active', 'deactivated_at', 'deactivated_by', 'updated_at'])
        VoucherChangeLog.objects.create(
            voucher=voucher,
            changed_by=request.user,
            changes={'action': 'deactivated', 'code': voucher.code},
        )
        return Response(VoucherSerializer(voucher).data)

    @action(detail=False, methods=['get'], url_path='report')
    @extend_schema(
        summary='Reporte de uso de vouchers (UC-PRO-04)',
        description=(
            'Lista vouchers con estadísticas de uso, agregados de órdenes y ROI. '
            'Filtros: ?status=, ?is_active=, ?date_from=YYYY-MM-DD, ?date_to=YYYY-MM-DD. '
            'Export: ?export=csv.'
        ),
        tags=['vouchers'],
        parameters=[
            OpenApiParameter('status', str, required=False,
                             description='ACTIVE|INACTIVE|EXPIRED|EXHAUSTED|NOT_YET_ACTIVE'),
            OpenApiParameter('is_active', bool, required=False),
            OpenApiParameter('date_from', str, required=False,
                             description='Filtrar ordenes desde esta fecha (YYYY-MM-DD).'),
            OpenApiParameter('date_to', str, required=False,
                             description='Filtrar ordenes hasta esta fecha (YYYY-MM-DD).'),
            OpenApiParameter('export', str, required=False,
                             description='csv para exportar en formato CSV.'),
        ],
        responses={200: VoucherReportSerializer(many=True)},
    )
    def report(self, request):
        qs = Voucher.all_objects.all().order_by('-current_uses')
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ('true', '1'))

        date_from = request.query_params.get('date_from')
        date_to   = request.query_params.get('date_to')

        # H-CICLO27-02: validar que date_from <= date_to antes de filtrar.
        # Sin esta validación, date_from > date_to produce queries vacías
        # silenciosas: orders_count=0 para todos los vouchers, sin error
        # visible. El admin podría interpretar erróneamente que no hubo usos.
        if date_from and date_to and date_from > date_to:
            raise ValidationError({
                'date_from': 'date_from no puede ser posterior a date_to.',
                'codigo_error': 'INVALID_DATE_RANGE',
            })

        orders_base = Order.objects.filter(voucher_code=OuterRef('code'))
        if date_from:
            orders_base = orders_base.filter(created_at__date__gte=date_from)
        if date_to:
            orders_base = orders_base.filter(created_at__date__lte=date_to)

        count_sq = (
            orders_base.values('voucher_code')
            .annotate(c=Count('id')).values('c')[:1]
        )
        disc_sq = (
            orders_base.values('voucher_code')
            .annotate(s=Sum('value__discount')).values('s')[:1]
        )
        rev_sq = (
            orders_base.values('voucher_code')
            .annotate(s=Sum('value__total')).values('s')[:1]
        )

        qs = qs.annotate(
            orders_count=Coalesce(
                Subquery(count_sq, output_field=IntegerField()), 0,
            ),
            total_discount_given=Subquery(
                disc_sq, output_field=DjDecimalField(max_digits=12, decimal_places=2),
            ),
            total_revenue_with_voucher=Subquery(
                rev_sq, output_field=DjDecimalField(max_digits=12, decimal_places=2),
            ),
        )

        data = VoucherReportSerializer(qs, many=True).data
        status_filter = request.query_params.get('status')
        if status_filter:
            data = [d for d in data if d['status'] == status_filter.upper()]

        if request.query_params.get('export') == 'csv':
            fieldnames = [
                'id', 'code', 'voucher_type', 'status',
                'current_uses', 'max_uses',
                'orders_count', 'total_discount_given',
                'total_revenue_with_voucher', 'roi',
                'valid_from', 'valid_until',
            ]
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for row in data:
                writer.writerow(dict(row))
            resp = HttpResponse(buf.getvalue(), content_type='text/csv')
            resp['Content-Disposition'] = 'attachment; filename="vouchers_report.csv"'
            return resp

        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            raise ValidationError({'page': 'Debe ser un entero valido.'})
        page_size = 20
        start = (page - 1) * page_size
        end   = start + page_size
        total = len(data)
        return Response({
            'count':    total,
            'page':     page,
            'pages':    (total + page_size - 1) // page_size or 1,
            'results':  data[start:end],
        })

    @extend_schema(summary='Listar vouchers', tags=['vouchers'],
                   responses={200: VoucherSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear voucher', tags=['vouchers'],
                   responses={201: VoucherSerializer, 400: None})
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar voucher (PATCH)', tags=['vouchers'],
                   responses={200: VoucherSerializer, 400: None})
    def partial_update(self, request, *args, **kwargs):
        # select_for_update inside atomic prevents a concurrent apply_voucher
        # from incrementing current_uses between our read and the final save,
        # which would otherwise allow mutating `code`/`voucher_type` on a
        # voucher that already has uses (TOCTOU race).
        with transaction.atomic():
            instance = Voucher.objects.select_for_update().get(pk=self.get_object().pk)
            if instance.current_uses > 0:
                for campo in ('code', 'voucher_type'):
                    if campo in request.data:
                        return Response(
                            {
                                'detail': f'El campo "{campo}" es inmutable cuando el voucher ya tiene usos.',
                                'codigo_error': 'FIELD_IMMUTABLE_WHILE_USED',
                            },
                            status=400,
                        )
            kwargs['partial'] = True
            return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Desactivar voucher',
        responses={204: None},
        tags=['vouchers'],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
