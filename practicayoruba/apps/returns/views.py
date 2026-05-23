"""
Views — apps.returns (P-12 / UC-RET-01..06).

Buyer:
  POST /api/v1/returns/                   UC-RET-01 create
  GET  /api/v1/returns/                   UC-RET-02 list own
  GET  /api/v1/returns/<id>/              UC-RET-02 detail

Admin:
  GET  /api/v1/admin/returns/             UC-RET-03 queue
  POST /api/v1/admin/returns/<id>/approve/    UC-RET-04
  POST /api/v1/admin/returns/<id>/reject/     UC-RET-04
  POST /api/v1/admin/returns/<id>/request-info/ UC-RET-05
  POST /api/v1/admin/returns/<id>/reception/  UC-RET-05
  POST /api/v1/admin/returns/<id>/refund/     UC-RET-06
"""
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.orders.models import Order
from .models import ReturnRequest
from .serializers import ReturnRequestAdminSerializer, ReturnRequestSerializer




class ReturnListCreateView(APIView):
    """
    GET  /api/v1/returns/ — UC-RET-02 list own returns.
    POST /api/v1/returns/ — UC-RET-01 create return request.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Listar mis devoluciones (UC-RET-02)',
        tags=['returns'],
        responses={200: ReturnRequestSerializer(many=True)},
    )
    def get(self, request):
        qs = ReturnRequest.objects.filter(
            order__user=request.user
        ).select_related('order').order_by('-created_at')
        return Response(ReturnRequestSerializer(qs, many=True).data)

    @extend_schema(
        summary='Solicitar devolución (UC-RET-01)',
        request=ReturnRequestSerializer,
        tags=['returns'],
        responses={201: ReturnRequestSerializer, 400: None},
    )
    def post(self, request):
        order_number = request.data.get('order_number')
        if not order_number:
            raise ValidationError({'order_number': 'Requerido.'})

        try:
            order = Order.objects.get(
                order_number=order_number, user=request.user
            )
        except Order.DoesNotExist:
            raise NotFound({'detail': 'Orden no encontrada.',
                            'codigo_error': 'ORDER_NOT_FOUND'})

        if order.status != Order.STATUS_DELIVERED:
            raise ValidationError({
                'detail': 'Solo se pueden devolver órdenes entregadas.',
                'codigo_error': 'ORDER_NOT_DELIVERED',
            })

        if ReturnRequest.objects.filter(order=order).exists():
            raise ValidationError({
                'detail': 'Ya existe una solicitud de devolución para esta orden.',
                'codigo_error': 'RETURN_DUPLICATE',
            })

        reason = (request.data.get('reason') or '').strip()
        if not reason:
            raise ValidationError({'reason': 'El motivo es requerido.'})

        ret = ReturnRequest.objects.create(
            order=order,
            reason=reason,
            status=ReturnRequest.STATUS_PENDING,
        )
        return Response(
            ReturnRequestSerializer(ret).data,
            status=status.HTTP_201_CREATED,
        )


class ReturnDetailView(APIView):
    """GET /api/v1/returns/<id>/ — UC-RET-02 detail."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Detalle de devolución (UC-RET-02)',
        tags=['returns'],
        responses={200: ReturnRequestSerializer, 404: None},
    )
    def get(self, request, pk):
        try:
            ret = ReturnRequest.objects.select_related('order').get(
                pk=pk, order__user=request.user
            )
        except ReturnRequest.DoesNotExist:
            raise NotFound({'detail': 'Devolución no encontrada.',
                            'codigo_error': 'RETURN_NOT_FOUND'})
        return Response(ReturnRequestSerializer(ret).data)


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminReturnListView(_AdminOnly, APIView):
    """GET /api/v1/admin/returns/ — UC-RET-03."""

    @extend_schema(
        summary='Cola de devoluciones (admin) (UC-RET-03)',
        parameters=[OpenApiParameter('status', str, required=False)],
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer(many=True)},
    )
    def get(self, request):
        status_filter = request.query_params.get('status')
        qs = ReturnRequest.objects.all().select_related('order__user').order_by('-created_at')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(ReturnRequestAdminSerializer(qs, many=True).data)


class AdminReturnApproveView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/approve/ — UC-RET-04."""

    @extend_schema(
        summary='Aprobar devolución (UC-RET-04)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 400: None, 404: None},
    )
    def post(self, request, pk):
        try:
            ret = ReturnRequest.objects.get(pk=pk)
        except ReturnRequest.DoesNotExist:
            raise NotFound({'detail': 'Devolución no encontrada.',
                            'codigo_error': 'RETURN_NOT_FOUND'})
        if ret.status != ReturnRequest.STATUS_PENDING:
            raise ValidationError({'detail': 'Solo se pueden aprobar devoluciones pendientes.',
                                    'codigo_error': 'INVALID_STATUS'})
        ret.status = ReturnRequest.STATUS_APPROVED
        ret.reviewed_at = timezone.now()
        ret.reviewed_by = request.user
        ret.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
        return Response(ReturnRequestAdminSerializer(ret).data)


class AdminReturnRejectView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/reject/ — UC-RET-04."""

    @extend_schema(
        summary='Rechazar devolución (UC-RET-04)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 400: None, 404: None},
    )
    def post(self, request, pk):
        try:
            ret = ReturnRequest.objects.get(pk=pk)
        except ReturnRequest.DoesNotExist:
            raise NotFound({'detail': 'Devolución no encontrada.',
                            'codigo_error': 'RETURN_NOT_FOUND'})
        if ret.status != ReturnRequest.STATUS_PENDING:
            raise ValidationError({'detail': 'Solo se pueden rechazar devoluciones pendientes.',
                                    'codigo_error': 'INVALID_STATUS'})
        reject_reason = (request.data.get('reason') or '').strip()
        ret.status = ReturnRequest.STATUS_REJECTED
        ret.reject_reason = reject_reason
        ret.reviewed_at = timezone.now()
        ret.reviewed_by = request.user
        ret.save(update_fields=['status', 'reject_reason', 'reviewed_at', 'reviewed_by'])
        return Response(ReturnRequestAdminSerializer(ret).data)


class AdminReturnRequestInfoView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/request-info/ — UC-RET-05."""

    @extend_schema(
        summary='Solicitar información adicional (UC-RET-05)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 404: None},
    )
    def post(self, request, pk):
        try:
            ret = ReturnRequest.objects.get(pk=pk)
        except ReturnRequest.DoesNotExist:
            raise NotFound({'detail': 'Devolución no encontrada.',
                            'codigo_error': 'RETURN_NOT_FOUND'})
        ret.status = ReturnRequest.STATUS_INFO_REQUESTED
        ret.save(update_fields=['status'])
        return Response(ReturnRequestAdminSerializer(ret).data)


class AdminReturnReceptionView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/reception/ — UC-RET-05 recepción física."""

    @extend_schema(
        summary='Registrar recepción física del producto (UC-RET-05)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 404: None},
    )
    def post(self, request, pk):
        try:
            ret = ReturnRequest.objects.get(pk=pk)
        except ReturnRequest.DoesNotExist:
            raise NotFound({'detail': 'Devolución no encontrada.',
                            'codigo_error': 'RETURN_NOT_FOUND'})
        ret.status = ReturnRequest.STATUS_RECEIVED
        ret.received_at = timezone.now()
        ret.save(update_fields=['status', 'received_at'])
        return Response(ReturnRequestAdminSerializer(ret).data)


class AdminReturnRefundView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/refund/ — UC-RET-06."""

    @extend_schema(
        summary='Procesar reembolso (UC-RET-06)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 400: None, 404: None},
    )
    def post(self, request, pk):
        try:
            ret = ReturnRequest.objects.get(pk=pk)
        except ReturnRequest.DoesNotExist:
            raise NotFound({'detail': 'Devolución no encontrada.',
                            'codigo_error': 'RETURN_NOT_FOUND'})
        if ret.status != ReturnRequest.STATUS_RECEIVED:
            raise ValidationError({
                'detail': 'Solo se puede reembolsar una devolución en estado RECEIVED.',
                'codigo_error': 'INVALID_STATUS',
            })
        ret.status = ReturnRequest.STATUS_REFUNDED
        ret.refunded_at = timezone.now()
        ret.save(update_fields=['status', 'refunded_at'])
        return Response(ReturnRequestAdminSerializer(ret).data)
