"""
Views — apps.returns (UC-RET-01..06).

User endpoints:
  POST   /api/v1/returns/                          UC-RET-01 create
  GET    /api/v1/returns/                          UC-RET-04 list own
  GET    /api/v1/returns/{id}/                     UC-RET-04 detail own

Admin endpoints:
  GET    /api/v1/admin/returns/                    UC-RET-05 queue + metrics
  GET    /api/v1/admin/returns/{id}/               admin detail
  POST   /api/v1/admin/returns/{id}/approve/       UC-RET-02 approve
  POST   /api/v1/admin/returns/{id}/reject/        UC-RET-02 reject
  POST   /api/v1/admin/returns/{id}/request-info/  UC-RET-02 Alt B
  POST   /api/v1/admin/returns/{id}/reception/     UC-RET-03 register reception
  POST   /api/v1/admin/returns/{id}/refund/        UC-RET-06 process refund
"""
from django.db import transaction
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.users.audit import audit_log_business
from apps.users.models import BusinessEvent
from apps.orders.models import Order as OrderModel
from apps.payments.models import Payment
from apps.payments.services import execute_refund
from .models import ReturnHistoryEntry, ReturnItem, ReturnRequest
from .serializers import AdminReturnDetailSerializer, AdminReturnListSerializer, ReturnApproveSerializer, ReturnCreateSerializer, ReturnDetailSerializer, ReturnInfoRequestSerializer, ReturnListSerializer, ReturnReceptionSerializer, ReturnRefundSerializer, ReturnRejectSerializer
from apps.notifications.service import notify_return_processed



def _get_own_return(return_id, user):
    """
    Devuelve la solicitud si pertenece al user (o si user.is_staff).
    Si no existe o pertenece a otro comprador -> Http404 (RNF-SEC-003).
    """
    qs = ReturnRequest.objects.all()
    obj = get_object_or_404(qs, pk=return_id)
    if not user.is_staff and obj.user_id != user.id:
        raise Http404
    return obj


def _get_admin_return(return_id):
    return get_object_or_404(ReturnRequest.objects.all(), pk=return_id)


def _record_history(return_request, status_to, actor, justification=''):
    return ReturnHistoryEntry.objects.create(
        return_request=return_request,
        status_to=status_to,
        actor=actor,
        justification=justification or '',
    )


# ────────────────────────────── UC-RET-01 / UC-RET-04 ────────────────────
class ReturnListCreateView(APIView):
    """POST crear solicitud / GET listar devoluciones del comprador."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Listar mis devoluciones',
        tags=['returns'],
        responses=ReturnListSerializer(many=True),
    )
    def get(self, request):
        qs = ReturnRequest.objects.filter(user=request.user)
        return Response(ReturnListSerializer(qs, many=True).data)

    @extend_schema(
        summary='Solicitar devolucion',
        tags=['returns'],
        request=ReturnCreateSerializer,
        responses={201: ReturnDetailSerializer},
    )
    def post(self, request):
        serializer = ReturnCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        # Idempotencia: AC-05 UC-RET-01 - (user, order_id, item_id).
        # Permite solicitar devolucion de items distintos de la misma orden,
        # bloqueando solo si los items se solapan con una solicitud pendiente
        # existente. Sin items en ninguna parte, se trata como colision por
        # orden (caso conservador).
        pending_qs = ReturnRequest.objects.filter(
            user=request.user,
            order_id=payload['order_id'],
            status=ReturnRequest.Status.PENDING_REVIEW,
        )
        incoming_product_ids = {
            item['product_id'] for item in payload.get('items') or []
        }
        conflict = False
        if not incoming_product_ids:
            conflict = pending_qs.exists()
        else:
            conflict = ReturnItem.objects.filter(
                return_request__in=pending_qs,
                product_id__in=incoming_product_ids,
            ).exists()
        if conflict:
            return Response(
                {'error_code': 'REQUEST_ALREADY_EXISTS',
                 'detail': 'Ya existe una solicitud pendiente para esa orden y items.'},
                status=status.HTTP_409_CONFLICT,
            )

        ret = ReturnRequest.objects.create(
            user=request.user,
            order_id=payload['order_id'],
            reason=payload['reason'],
            description=payload['description'],
        )
        for item in payload.get('items', []) or []:
            ReturnItem.objects.create(
                return_request=ret,
                product_id=item['product_id'],
                quantity=item.get('quantity', 1),
            )
        _record_history(
            ret, ReturnRequest.Status.PENDING_REVIEW, request.user,
            justification='Solicitud creada por el comprador.',
        )
        audit_log_business(
            request.user, BusinessEvent.ACTION_RETURN_REQUESTED, request,
            target_type=BusinessEvent.TARGET_RETURN, target_id=ret.pk,
            extra={'order_id': payload['order_id'], 'reason': payload['reason']},
        )
        return Response(
            ReturnDetailSerializer(ret).data,
            status=status.HTTP_201_CREATED,
        )


class ReturnDetailView(APIView):
    """GET detalle de devolucion propia (o cualquiera si is_staff)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Detalle de devolucion (comprador)',
        tags=['returns'],
        responses=ReturnDetailSerializer,
    )
    def get(self, request, return_id):
        ret = _get_own_return(return_id, request.user)
        return Response(ReturnDetailSerializer(ret).data)


# ────────────────────────────── UC-RET-05 ────────────────────────────────
ADMIN_ACTIVE_STATUSES = (
    ReturnRequest.Status.PENDING_REVIEW,
    ReturnRequest.Status.INFO_REQUESTED,
    ReturnRequest.Status.APPROVED,
    ReturnRequest.Status.RECEIVED,
)


class AdminReturnListView(ListAPIView):
    """UC-RET-05 — bandeja admin con bloque metrics."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = AdminReturnListSerializer

    @extend_schema(
        summary='Bandeja de devoluciones (admin)',
        tags=['returns'],
        parameters=[
            OpenApiParameter('status', str, required=False),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def list(self, request, *args, **kwargs):
        qs = ReturnRequest.objects.all().order_by('created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        metrics_qs = (
            ReturnRequest.objects.values('status').annotate(total=Count('id'))
        )
        counts = {row['status']: row['total'] for row in metrics_qs}
        metrics = {
            'pendientes': counts.get(ReturnRequest.Status.PENDING_REVIEW, 0),
            'aprobadas': counts.get(ReturnRequest.Status.APPROVED, 0),
            'pendiente_info': counts.get(ReturnRequest.Status.INFO_REQUESTED, 0),
            'recibidas': counts.get(ReturnRequest.Status.RECEIVED, 0),
            'rechazadas': counts.get(ReturnRequest.Status.REJECTED, 0),
            'reembolsadas': counts.get(ReturnRequest.Status.REFUNDED, 0),
        }
        results = AdminReturnListSerializer(qs, many=True).data
        return Response({'results': results, 'metrics': metrics})

    def get_queryset(self):  # pragma: no cover (overridden by list)
        return ReturnRequest.objects.all()


class AdminReturnDetailView(APIView):
    """Detalle admin extendido."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Detalle de devolucion (admin)',
        tags=['returns'],
        responses=AdminReturnDetailSerializer,
    )
    def get(self, request, return_id):
        ret = _get_admin_return(return_id)
        return Response(AdminReturnDetailSerializer(ret).data)


# ────────────────────────────── UC-RET-02 actions ────────────────────────
class AdminReturnApproveView(APIView):
    """POST /admin/returns/{id}/approve/ — UC-RET-02 aprobar."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Aprobar solicitud de devolucion',
        tags=['returns'],
        request=ReturnApproveSerializer,
        responses=AdminReturnDetailSerializer,
    )
    def post(self, request, return_id):
        ret = _get_admin_return(return_id)
        if ret.status not in (
            ReturnRequest.Status.PENDING_REVIEW,
            ReturnRequest.Status.INFO_REQUESTED,
        ):
            return Response(
                {'error_code': 'INVALID_STATE',
                 'detail': 'La solicitud no esta en un estado revisable.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        serializer = ReturnApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            ret.status = ReturnRequest.Status.APPROVED
            ret.rejection_reason = ''
            ret.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            _record_history(
                ret, ReturnRequest.Status.APPROVED, request.user,
                justification=serializer.validated_data['justification'],
            )
            audit_log_business(
                request.user, BusinessEvent.ACTION_RETURN_RESOLVED, request,
                target_type=BusinessEvent.TARGET_RETURN, target_id=ret.pk,
                extra={'resolution': 'APPROVED'},
            )
            ret_order = OrderModel.objects.filter(pk=ret.order_id).first()
            if ret_order:
                notify_return_processed(
                    order=ret_order,
                    user=ret.user,
                    return_status='APPROVED',
                    reason=None,
                )
        return Response(AdminReturnDetailSerializer(ret).data)


class AdminReturnRejectView(APIView):
    """POST /admin/returns/{id}/reject/ — UC-RET-02 rechazar."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Rechazar solicitud de devolucion',
        tags=['returns'],
        request=ReturnRejectSerializer,
        responses=AdminReturnDetailSerializer,
    )
    def post(self, request, return_id):
        ret = _get_admin_return(return_id)
        if ret.status not in (
            ReturnRequest.Status.PENDING_REVIEW,
            ReturnRequest.Status.INFO_REQUESTED,
        ):
            return Response(
                {'error_code': 'INVALID_STATE',
                 'detail': 'La solicitud no esta en un estado revisable.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        serializer = ReturnRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        justification = serializer.validated_data['justification']
        with transaction.atomic():
            ret.status = ReturnRequest.Status.REJECTED
            ret.rejection_reason = justification
            ret.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            _record_history(
                ret, ReturnRequest.Status.REJECTED, request.user,
                justification=justification,
            )
            audit_log_business(
                request.user, BusinessEvent.ACTION_RETURN_RESOLVED, request,
                target_type=BusinessEvent.TARGET_RETURN, target_id=ret.pk,
                extra={'resolution': 'REJECTED'},
            )
            ret_order = OrderModel.objects.filter(pk=ret.order_id).first()
            if ret_order:
                notify_return_processed(
                    order=ret_order,
                    user=ret.user,
                    return_status='REJECTED',
                    reason=justification,
                )
        return Response(AdminReturnDetailSerializer(ret).data)


class AdminReturnRequestInfoView(APIView):
    """POST /admin/returns/{id}/request-info/ — UC-RET-02 Alt B."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Solicitar informacion adicional al comprador',
        tags=['returns'],
        request=ReturnInfoRequestSerializer,
        responses=AdminReturnDetailSerializer,
    )
    def post(self, request, return_id):
        ret = _get_admin_return(return_id)
        if ret.status != ReturnRequest.Status.PENDING_REVIEW:
            return Response(
                {'error_code': 'INVALID_STATE',
                 'detail': 'Solo se puede pedir info a solicitudes pendientes.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        serializer = ReturnInfoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.validated_data['message']
        ret.status = ReturnRequest.Status.INFO_REQUESTED
        ret.save(update_fields=['status', 'updated_at'])
        _record_history(
            ret, ReturnRequest.Status.INFO_REQUESTED, request.user,
            justification=message,
        )
        return Response(AdminReturnDetailSerializer(ret).data)


# ────────────────────────────── UC-RET-03 reception ────────────────────────
class AdminReturnReceptionView(APIView):
    """POST /admin/returns/{id}/reception/ — UC-RET-03 recepcion fisica."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Registrar recepcion fisica del producto',
        tags=['returns'],
        request=ReturnReceptionSerializer,
        responses=AdminReturnDetailSerializer,
    )
    def post(self, request, return_id):
        ret = _get_admin_return(return_id)
        if ret.status != ReturnRequest.Status.APPROVED:
            return Response(
                {'error_code': 'REQUEST_NOT_APPROVED',
                 'detail': 'La solicitud debe estar APPROVED para registrar '
                           'recepcion.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if ret.received_at is not None:
            return Response(
                {'error_code': 'INVALID_STATE',
                 'detail': 'La recepcion ya fue registrada.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        serializer = ReturnReceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ret.received_at = data.get('received_at') or timezone.now()
        ret.status = ReturnRequest.Status.RECEIVED
        ret.save(update_fields=['received_at', 'status', 'updated_at'])

        # Persistir condicion del producto en cada item (UC-RET-03 AC-04).
        condition = data['product_condition']
        ret.items.update(product_condition=condition)

        notes = data.get('observations') or ''
        justification = f'product_condition={condition}'
        if notes:
            justification = f'{justification}; notes={notes}'
        _record_history(
            ret, ReturnRequest.Status.RECEIVED, request.user,
            justification=justification,
        )
        return Response(AdminReturnDetailSerializer(ret).data)


# ────────────────────────────── UC-RET-06 refund ───────────────────────────
class AdminReturnRefundView(APIView):
    """POST /admin/returns/{id}/refund/ — UC-RET-06 procesar reembolso."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Procesar reembolso de devolucion',
        tags=['returns'],
        request=ReturnRefundSerializer,
        responses=AdminReturnDetailSerializer,
    )
    def post(self, request, return_id):
        ret = _get_admin_return(return_id)
        if ret.refund_at is not None:
            return Response(
                {'error_code': 'REFUND_ALREADY_PROCESSED',
                 'detail': 'Ya se proceso el reembolso para esta solicitud.'},
                status=status.HTTP_409_CONFLICT,
            )
        if ret.status not in (
            ReturnRequest.Status.APPROVED,
            ReturnRequest.Status.RECEIVED,
        ):
            return Response(
                {'error_code': 'INVALID_STATE',
                 'detail': 'La solicitud no esta lista para reembolso.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        serializer = ReturnRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']

        payment = (
            Payment.objects
            .filter(
                order_id=ret.order_id,
                status__in=(
                    Payment.STATUS_APPROVED,
                    Payment.STATUS_PARTIALLY_REFUNDED,
                ),
            )
            .order_by('-id')
            .first()
        )
        if payment is None:
            return Response(
                {'error_code': 'PAYMENT_NOT_FOUND',
                 'detail': 'No hay un pago reembolsable asociado a esta orden.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            refund = execute_refund(
                payment=payment,
                amount=amount,
                reason=f'ReturnRequest #{ret.pk}',
                initiated_by=request.user,
            )
        except ValueError as exc:
            return Response(
                {'error_code': 'INVALID_REFUND_AMOUNT', 'detail': str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except RuntimeError as exc:
            return Response(
                {'error_code': 'GATEWAY_ERROR', 'detail': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        ret.refund_amount = refund.amount
        ret.refund_at = timezone.now()
        ret.status = ReturnRequest.Status.REFUNDED
        ret.save(update_fields=[
            'refund_amount', 'refund_at', 'status', 'updated_at',
        ])
        _record_history(
            ret, ReturnRequest.Status.REFUNDED, request.user,
            justification=(
                f'Reembolso procesado por {refund.amount} '
                f'(gateway_refund_id={refund.gateway_refund_id}).'
            ),
        )
        return Response(AdminReturnDetailSerializer(ret).data)
