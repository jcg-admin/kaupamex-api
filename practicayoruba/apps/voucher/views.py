"""
Views — apps.voucher (Sprint 13)
UC-PRO-01: Crear Voucher
UC-PRO-02: Editar Voucher
UC-PRO-03: Desactivar Voucher
UC-PRO-04: Reporte de Uso
"""
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.generics import ListAPIView

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
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        old = {f: getattr(self.get_object(), f)
               for f in serializer.validated_data}
        instance = serializer.save()
        # Registrar cambios en VoucherChangeLog (UC-PRO-02)
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
        """Soft delete: is_active=False. UC-PRO-03."""
        instance.is_active      = False
        instance.deactivated_at = timezone.now()
        instance.deactivated_by = self.request.user
        instance.save(update_fields=['is_active', 'deactivated_at', 'deactivated_by'])

    @action(detail=True, methods=['post'], url_path='activate')
    @extend_schema(
        summary='Reactivar voucher desactivado',
        responses={200: VoucherSerializer},
        tags=['vouchers'],
    )
    def activate(self, request, pk=None):
        voucher = self.get_object()
        if voucher.is_active:
            return Response({'detail': 'El voucher ya está activo.'}, status=400)
        voucher.is_active      = True
        voucher.deactivated_at = None
        voucher.deactivated_by = None
        voucher.save(update_fields=['is_active', 'deactivated_at', 'deactivated_by'])
        return Response(VoucherSerializer(voucher).data)

    @action(detail=False, methods=['get'], url_path='report')
    @extend_schema(
        summary='Reporte de uso de vouchers',
        description='Lista vouchers con estadísticas de uso. ROI con orders en Sprint 18.',
        tags=['vouchers'],
    )
    def report(self, request):
        qs = Voucher.objects.all().order_by('-current_uses')
        data = VoucherReportSerializer(qs, many=True).data
        return Response({'count': len(data), 'results': data})

    @extend_schema(summary='Listar vouchers', tags=['vouchers'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear voucher', tags=['vouchers'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar voucher (PATCH)', tags=['vouchers'])
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Desactivar voucher',
        responses={204: None},
        tags=['vouchers'],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
