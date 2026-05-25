"""
Views — apps.returns (P-12 / UC-RET-01..06).

Buyer:
  POST /api/v1/returns/                   UC-RET-01 create
  GET  /api/v1/returns/                   UC-RET-04 list own
  GET  /api/v1/returns/<id>/              UC-RET-04 detail

Admin:
  GET  /api/v1/admin/returns/             UC-RET-05 queue
  GET  /api/v1/admin/returns/<id>/        UC-RET-05 detail
  POST /api/v1/admin/returns/<id>/approve/    UC-RET-02
  POST /api/v1/admin/returns/<id>/reject/     UC-RET-02
  POST /api/v1/admin/returns/<id>/request-info/ UC-RET-02
  POST /api/v1/admin/returns/<id>/reception/  UC-RET-03
  POST /api/v1/admin/returns/<id>/refund/     UC-RET-06
"""
from decimal import Decimal
from django.db.models import Count, Q
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment, Refund
from apps.payments.services import execute_refund
from .models import ReturnHistoryEntry, ReturnItem, ReturnRequest
from .serializers import (
    ReturnRequestAdminSerializer,
    ReturnRequestSerializer,
    ReturnCreateSerializer,
    ReturnReceptionSerializer,
    ReturnRefundSerializer,
    ReturnApproveSerializer,
    ReturnRejectSerializer,
    ReturnInfoRequestSerializer,
)


def _get_return_or_404(pk):
    """Fetch ReturnRequest con select_related/prefetch para evitar N+1 al
    serializar con ReturnRequestAdminSerializer (user, items, history)."""
    try:
        return ReturnRequest.objects.select_related('user').prefetch_related(
            'items', 'history_entries__actor'
        ).get(pk=pk)
    except ReturnRequest.DoesNotExist:
        raise NotFound({'detail': 'Devolución no encontrada.',
                        'error_code': 'RETURN_NOT_FOUND'})


def _invalid_state_response(message='Estado inválido.', error_code='INVALID_STATE'):
    return Response(
        {'detail': message, 'error_code': error_code},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


class ReturnListCreateView(APIView):
    """
    GET  /api/v1/returns/ — UC-RET-04 list own returns.
    POST /api/v1/returns/ — UC-RET-01 create return request.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Listar mis devoluciones (UC-RET-04)',
        tags=['returns'],
        responses={200: ReturnRequestSerializer(many=True)},
    )
    def get(self, request):
        qs = ReturnRequest.objects.filter(
            user=request.user
        ).prefetch_related('items', 'history_entries__actor').order_by('-created_at')
        serializer = ReturnRequestSerializer(qs, many=True)
        return Response({'results': serializer.data})

    @extend_schema(
        summary='Solicitar devolución (UC-RET-01)',
        request=ReturnCreateSerializer,
        tags=['returns'],
        responses={201: ReturnRequestSerializer, 400: None, 409: None},
    )
    def post(self, request):
        ser = ReturnCreateSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        data = ser.validated_data
        order_number = data['order_number']
        reason = data['reason']
        description = data['description']
        items_data = data.get('items', [])

        # H-API-29: validar que la orden pertenece al usuario autenticado.
        # Sin este check un usuario podia crear devoluciones para ordenes ajenas.
        # H-CICLO38-01: lookup por order_number (identificador visible al
        # comprador) en lugar del PK interno. La UI siempre muestra/enlaza
        # order_number; usar el PK requeria que el comprador conociera el
        # ID interno de BD, lo cual nunca fue expuesto en la interfaz.
        try:
            order = Order.objects.get(order_number=order_number, user=request.user)
        except Order.DoesNotExist:
            raise DRFValidationError({
                'order_number': 'Orden no encontrada.',
                'codigo_error': 'ORDER_NOT_FOUND',
            })

        order_id = order.pk

        # H-API-31: solo se permiten devoluciones sobre ordenes ENTREGADAS.
        if order.status != Order.STATUS_DELIVERED:
            raise DRFValidationError({
                'order_number': 'Solo se pueden solicitar devoluciones para ordenes entregadas.',
                'codigo_error': 'ORDER_NOT_DELIVERED',
            })

        # H-CICLO34-03: límite de 30 días desde la entrega para solicitar devolución.
        # updated_at refleja el momento en que la orden pasó a DELIVERED ya que es
        # el último cambio de estado de la misma.
        RETURN_WINDOW_DAYS = 30
        delivery_ts = order.updated_at
        if delivery_ts and (timezone.now() - delivery_ts).days > RETURN_WINDOW_DAYS:
            raise DRFValidationError({
                'order_number': (
                    f'El plazo para solicitar devolución ({RETURN_WINDOW_DAYS} días '
                    f'desde la entrega) ha expirado.'
                ),
                'codigo_error': 'RETURN_WINDOW_EXPIRED',
            })

        # H-RET-QTY: validar que la cantidad devuelta no exceda la comprada.
        # Sin este check un comprador podía declarar devolver 9999 unidades
        # de un producto que compró 1. Se coteja contra OrderItem por product.
        if items_data:
            # Construir mapa product_id→quantity_purchased desde la orden
            purchased_qtys = {
                oi.product_id: oi.quantity
                for oi in OrderItem.objects.filter(order_id=order_id)
            }
            for item_data in items_data:
                pid = item_data['product_id']
                requested_qty = item_data.get('quantity', 1)
                purchased_qty = purchased_qtys.get(pid)
                if purchased_qty is None:
                    raise DRFValidationError({
                        'items': f'El producto {pid} no pertenece a esta orden.',
                        'codigo_error': 'PRODUCT_NOT_IN_ORDER',
                    })
                if requested_qty > purchased_qty:
                    raise DRFValidationError({
                        'items': (
                            f'La cantidad solicitada ({requested_qty}) para el '
                            f'producto {pid} excede la cantidad comprada ({purchased_qty}).'
                        ),
                        'codigo_error': 'QUANTITY_EXCEEDS_PURCHASED',
                    })

        # UC-RET-01 idempotency: check for overlapping pending requests
        # DEC-RET-03: if items are provided, check item-level overlap
        existing_qs = ReturnRequest.objects.filter(
            user=request.user,
            order_id=order_id,
            status__in=[
                ReturnRequest.Status.PENDING_REVIEW,
                ReturnRequest.Status.INFO_REQUESTED,
            ],
        )

        if items_data:
            # Check for item-level overlap with existing pending requests
            incoming_product_ids = {item['product_id'] for item in items_data}
            overlapping = False
            for existing in existing_qs:
                existing_product_ids = set(
                    existing.items.values_list('product_id', flat=True)
                )
                if existing_product_ids & incoming_product_ids:
                    overlapping = True
                    break
            if overlapping:
                return Response(
                    {'detail': 'Ya existe una solicitud pendiente con items solapados.',
                     'error_code': 'REQUEST_ALREADY_EXISTS'},
                    status=status.HTTP_409_CONFLICT,
                )
        else:
            # No items: any pending request for same order is a duplicate
            if existing_qs.exists():
                return Response(
                    {'detail': 'Ya existe una solicitud pendiente para esta orden.',
                     'error_code': 'REQUEST_ALREADY_EXISTS'},
                    status=status.HTTP_409_CONFLICT,
                )

        ret = ReturnRequest.objects.create(
            user=request.user,
            order_id=order_id,
            reason=reason,
            description=description,
            status=ReturnRequest.Status.PENDING_REVIEW,
        )

        # Create items if provided
        for item_data in items_data:
            ReturnItem.objects.create(
                return_request=ret,
                product_id=item_data['product_id'],
                quantity=item_data.get('quantity', 1),
            )

        # Create history entry
        ReturnHistoryEntry.objects.create(
            return_request=ret,
            status_to=ReturnRequest.Status.PENDING_REVIEW,
            actor=request.user,
            justification='Solicitud creada por el comprador.',
        )

        # Re-fetch con prefetch para evitar N+1 en ReturnRequestSerializer
        # (accede a items y history_entries__actor).
        ret = ReturnRequest.objects.prefetch_related(
            'items', 'history_entries__actor'
        ).get(pk=ret.pk)

        return Response(
            ReturnRequestSerializer(ret).data,
            status=status.HTTP_201_CREATED,
        )


class ReturnDetailView(APIView):
    """GET /api/v1/returns/<id>/ — UC-RET-04 detail."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Detalle de devolución (UC-RET-04)',
        tags=['returns'],
        responses={200: ReturnRequestSerializer, 404: None},
    )
    def get(self, request, return_id):
        try:
            ret = ReturnRequest.objects.prefetch_related(
                'items', 'history_entries__actor'
            ).get(pk=return_id, user=request.user)
        except ReturnRequest.DoesNotExist:
            raise NotFound({'detail': 'Devolución no encontrada.',
                            'error_code': 'RETURN_NOT_FOUND'})
        return Response(ReturnRequestSerializer(ret).data)


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminReturnListView(_AdminOnly, APIView):
    """GET /api/v1/admin/returns/ — UC-RET-05."""

    @extend_schema(
        summary='Cola de devoluciones (admin) (UC-RET-05)',
        parameters=[OpenApiParameter('status', str, required=False)],
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer(many=True)},
    )
    def get(self, request):
        status_filter = request.query_params.get('status')
        qs = ReturnRequest.objects.all().select_related('user').prefetch_related(
            'items', 'history_entries__actor'
        ).order_by('-created_at')
        if status_filter:
            qs = qs.filter(status=status_filter)

        results = ReturnRequestAdminSerializer(qs, many=True).data

        # Build metrics — single aggregate query instead of 6 separate COUNTs.
        # H-CICLO38-03: incluir `pendiente_info` (INFO_REQUESTED) para que
        # AdminReturnsPage pueda mostrar el contador correcto.
        counts = ReturnRequest.objects.aggregate(
            pendientes=Count('id', filter=Q(status=ReturnRequest.Status.PENDING_REVIEW)),
            aprobadas=Count('id', filter=Q(status=ReturnRequest.Status.APPROVED)),
            rechazadas=Count('id', filter=Q(status=ReturnRequest.Status.REJECTED)),
            recibidas=Count('id', filter=Q(status=ReturnRequest.Status.RECEIVED)),
            reembolsadas=Count('id', filter=Q(status=ReturnRequest.Status.REFUNDED)),
            pendiente_info=Count('id', filter=Q(status=ReturnRequest.Status.INFO_REQUESTED)),
        )
        metrics = counts

        return Response({'results': results, 'metrics': metrics})


class AdminReturnDetailView(_AdminOnly, APIView):
    """GET /api/v1/admin/returns/<return_id>/ — UC-RET-05 detail."""

    @extend_schema(
        summary='Detalle de devolución (admin) (UC-RET-05)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 404: None},
    )
    def get(self, request, return_id):
        try:
            ret = ReturnRequest.objects.select_related('user').prefetch_related(
                'items', 'history_entries__actor'
            ).get(pk=return_id)
        except ReturnRequest.DoesNotExist:
            raise NotFound({'detail': 'Devolución no encontrada.', 'error_code': 'RETURN_NOT_FOUND'})
        return Response(ReturnRequestAdminSerializer(ret).data)


class AdminReturnApproveView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/approve/ — UC-RET-02."""

    @extend_schema(
        summary='Aprobar devolución (UC-RET-02)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 422: None, 404: None},
    )
    def post(self, request, return_id):
        ser = ReturnApproveSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ret = _get_return_or_404(return_id)
        if ret.status != ReturnRequest.Status.PENDING_REVIEW:
            return _invalid_state_response(
                'Solo se pueden aprobar devoluciones en estado PENDING_REVIEW.',
                'INVALID_STATE',
            )

        justification = ser.validated_data['justification']
        ret.status = ReturnRequest.Status.APPROVED
        ret.save(update_fields=['status', 'updated_at'])

        ReturnHistoryEntry.objects.create(
            return_request=ret,
            status_to=ReturnRequest.Status.APPROVED,
            actor=request.user,
            justification=justification,
        )

        return Response(ReturnRequestAdminSerializer(ret).data)


class AdminReturnRejectView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/reject/ — UC-RET-02."""

    @extend_schema(
        summary='Rechazar devolución (UC-RET-02)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 422: None, 404: None},
    )
    def post(self, request, return_id):
        ser = ReturnRejectSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ret = _get_return_or_404(return_id)
        if ret.status != ReturnRequest.Status.PENDING_REVIEW:
            return _invalid_state_response(
                'Solo se pueden rechazar devoluciones en estado PENDING_REVIEW.',
                'INVALID_STATE',
            )

        justification = ser.validated_data['justification']
        ret.rejection_reason = justification
        ret.status = ReturnRequest.Status.REJECTED
        ret.save(update_fields=['status', 'rejection_reason', 'updated_at'])

        ReturnHistoryEntry.objects.create(
            return_request=ret,
            status_to=ReturnRequest.Status.REJECTED,
            actor=request.user,
            justification=justification,
        )

        return Response(ReturnRequestAdminSerializer(ret).data)


class AdminReturnRequestInfoView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/request-info/ — UC-RET-02 Alt B."""

    @extend_schema(
        summary='Solicitar información adicional (UC-RET-02)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 422: None, 404: None},
    )
    def post(self, request, return_id):
        ser = ReturnInfoRequestSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ret = _get_return_or_404(return_id)
        if ret.status != ReturnRequest.Status.PENDING_REVIEW:
            return _invalid_state_response(
                'Solo se puede solicitar información para devoluciones en estado PENDING_REVIEW.',
                'INVALID_STATE',
            )

        message = ser.validated_data['message']
        ret.status = ReturnRequest.Status.INFO_REQUESTED
        ret.save(update_fields=['status', 'updated_at'])

        ReturnHistoryEntry.objects.create(
            return_request=ret,
            status_to=ReturnRequest.Status.INFO_REQUESTED,
            actor=request.user,
            justification=message,
        )

        return Response(ReturnRequestAdminSerializer(ret).data)


class AdminReturnReceptionView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/reception/ — UC-RET-03."""

    @extend_schema(
        summary='Registrar recepción física del producto (UC-RET-03)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 422: None, 404: None},
    )
    def post(self, request, return_id):
        ser = ReturnReceptionSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ret = _get_return_or_404(return_id)
        if ret.status != ReturnRequest.Status.APPROVED:
            return Response(
                {'detail': 'Solo se puede registrar recepción para devoluciones APPROVED.',
                 'error_code': 'REQUEST_NOT_APPROVED'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        ret.status = ReturnRequest.Status.RECEIVED
        ret.received_at = timezone.now()
        ret.save(update_fields=['status', 'received_at', 'updated_at'])

        ReturnHistoryEntry.objects.create(
            return_request=ret,
            status_to=ReturnRequest.Status.RECEIVED,
            actor=request.user,
            justification=ser.validated_data.get('observations', ''),
        )

        return Response(ReturnRequestAdminSerializer(ret).data)


class AdminReturnRefundView(_AdminOnly, APIView):
    """POST /api/v1/admin/returns/<id>/refund/ — UC-RET-06."""

    @extend_schema(
        summary='Procesar reembolso (UC-RET-06)',
        tags=['returns'],
        responses={200: ReturnRequestAdminSerializer, 422: None, 409: None, 404: None},
    )
    def post(self, request, return_id):
        ser = ReturnRefundSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        ret = _get_return_or_404(return_id)

        # Idempotency check — runs before general state check
        if ret.status == ReturnRequest.Status.REFUNDED or ret.refund_at is not None:
            return Response(
                {'detail': 'El reembolso ya fue procesado.',
                 'error_code': 'REFUND_ALREADY_PROCESSED'},
                status=status.HTTP_409_CONFLICT,
            )

        # Must be in APPROVED status to refund
        if ret.status not in (ReturnRequest.Status.APPROVED, ReturnRequest.Status.RECEIVED):
            return _invalid_state_response(
                'Solo se puede reembolsar una devolución en estado APPROVED o RECEIVED.',
                'INVALID_STATE',
            )

        # Check if already refunded (after state change)
        amount = ser.validated_data['amount']

        # H-RET-R01: include PARTIALLY_REFUNDED so second partial refunds work.
        try:
            payment = Payment.objects.filter(
                order_id=ret.order_id,
                status__in=[Payment.STATUS_APPROVED, Payment.STATUS_PARTIALLY_REFUNDED],
            ).latest('created_at')
        except Payment.DoesNotExist:
            return Response(
                {'detail': 'No se encontró un pago aprobado para esta orden.',
                 'error_code': 'PAYMENT_NOT_FOUND'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # H-RET-R01: delegate to execute_refund() which handles partial vs full
        # refund status, creates the Refund record, and notifies atomically.
        # Direct gateway call + unconditional STATUS_REFUNDED was incorrect.
        try:
            execute_refund(
                payment=payment,
                amount=amount,
                reason=f'Devolución #{ret.pk} aprobada por admin',
                initiated_by=request.user,
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc), 'error_code': 'PAYMENT_NOT_REFUNDABLE'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as exc:
            return Response(
                {'detail': f'Error al procesar el reembolso: {exc}',
                 'error_code': 'GATEWAY_ERROR'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        with transaction.atomic():
            ret.status = ReturnRequest.Status.REFUNDED
            ret.refund_amount = amount
            ret.refund_at = timezone.now()
            ret.save(update_fields=['status', 'refund_amount', 'refund_at', 'updated_at'])

            ReturnHistoryEntry.objects.create(
                return_request=ret,
                status_to=ReturnRequest.Status.REFUNDED,
                actor=request.user,
                justification=f'Reembolso de {amount} procesado.',
            )

        return Response(ReturnRequestAdminSerializer(ret).data)
