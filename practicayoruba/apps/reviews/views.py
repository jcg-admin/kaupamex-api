"""
Views — apps.reviews (P-14 / UC-REV-01..03).

Public:
  GET  /api/v1/products/<product_id>/reviews/      Approved only + stats.
  POST /api/v1/products/<product_id>/reviews/      Create (auth required).

Admin:
  GET  /api/v1/admin/reviews/?status=PENDING_MODERATION  FIFO queue.
  POST /api/v1/admin/reviews/<id>/approve/         Idempotent.
  POST /api/v1/admin/reviews/<id>/reject/          With reason.

Spanish business error codes per DEC-DOC-006. Audit log per RNF-AUDIT-001.
"""
from collections import Counter
from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.catalogue.models import Product
from apps.orders.models import Order
from .models import Review, ReviewModerationLog
from .serializers import ReviewAdminSerializer, ReviewCreateSerializer, ReviewPublicSerializer





# =============================================================================
# Public — list + create per product
# =============================================================================

class ProductReviewsView(APIView):
    """GET (public) / POST (auth) /api/v1/products/<product_id>/reviews/."""

    serializer_class = ReviewPublicSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]

    @extend_schema(
        summary='List approved reviews for product (UC-REV-01).',
        tags=['reviews'],
    )
    def get(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise NotFound({
                'detail': 'Producto no encontrado.',
                'codigo_error': 'PRODUCTO_NO_ENCONTRADO',
            })

        approved = Review.objects.filter(
            product=product, status=Review.STATUS_APPROVED,
        ).select_related('user').order_by('-created_at')

        ratings = list(approved.values_list('rating', flat=True))
        total = len(ratings)
        avg = round(sum(ratings) / total, 2) if total else 0.0
        breakdown = Counter(ratings)
        rating_breakdown = {str(i): breakdown.get(i, 0) for i in range(1, 6)}

        return Response({
            'product_id': product.id,
            'average_rating': avg,
            'total_reviews': total,
            'rating_breakdown': rating_breakdown,
            'results': ReviewPublicSerializer(approved, many=True).data,
        })

    @extend_schema(
        summary='Create review (UC-REV-02).',
        request=ReviewCreateSerializer,
        tags=['reviews'],
    )
    @transaction.atomic
    def post(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise NotFound({
                'detail': 'Producto no encontrado.',
                'codigo_error': 'PRODUCTO_NO_ENCONTRADO',
            })

        ser = ReviewCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Order ownership check + product purchased.
        try:
            order = Order.objects.get(pk=data['order_id'])
        except Order.DoesNotExist:
            raise NotFound({
                'detail': 'Orden no encontrada.',
                'codigo_error': 'ORDEN_NO_ENCONTRADA',
            })
        if order.user_id != request.user.id:
            raise PermissionDenied({
                'detail': 'No puedes reseñar productos que no compraste.',
                'codigo_error': 'PRODUCTO_NO_COMPRADO',
            })
        if not order.items.filter(product=product).exists():
            raise PermissionDenied({
                'detail': 'El producto no fue comprado en esa orden.',
                'codigo_error': 'PRODUCTO_NO_COMPRADO',
            })

        try:
            review = Review.objects.create(
                user=request.user,
                product=product,
                order=order,
                rating=data['rating'],
                title=data['title'],
                body=data['body'],
                status=Review.STATUS_PENDING,
            )
        except IntegrityError:
            raise ValidationError({
                'detail': 'Ya enviaste una reseña para este producto.',
                'codigo_error': 'RESENA_DUPLICADA',
            })

        return Response(
            ReviewAdminSerializer(review).data,
            status=status.HTTP_201_CREATED,
        )


# =============================================================================
# Admin — moderation queue + approve / reject
# =============================================================================

class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = ReviewAdminSerializer


class ReviewAdminListView(_AdminOnly, APIView):
    @extend_schema(
        summary='Moderation queue (UC-REV-03).',
        parameters=[OpenApiParameter('status', str, required=False)],
        tags=['reviews'],
    )
    def get(self, request):
        status_filter = request.query_params.get('status', Review.STATUS_PENDING)
        valid = {code for code, _ in Review.STATUSES}
        if status_filter not in valid:
            raise ValidationError({
                'detail': f'status invalido: {status_filter}.',
                'codigo_error': 'STATUS_INVALIDO',
            })
        qs = (
            Review.objects.filter(status=status_filter)
            .select_related('user', 'product', 'order')
            .order_by('created_at')  # FIFO
        )
        return Response(ReviewAdminSerializer(qs, many=True).data)


class ReviewApproveView(_AdminOnly, APIView):
    @extend_schema(
        summary='Approve review (idempotent).',
        tags=['reviews'],
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            review = Review.objects.select_for_update().get(pk=pk)
        except Review.DoesNotExist:
            raise NotFound({
                'detail': 'Reseña no encontrada.',
                'codigo_error': 'RESENA_NO_ENCONTRADA',
            })

        already = review.status == Review.STATUS_APPROVED
        if review.status == Review.STATUS_REJECTED:
            raise ValidationError({
                'detail': 'No se puede aprobar una reseña ya rechazada.',
                'codigo_error': 'RESENA_YA_RECHAZADA',
            })
        if not already:
            review.status = Review.STATUS_APPROVED
            review.reject_reason = ''
            review.moderated_at = timezone.now()
            review.moderated_by = request.user
            review.save(update_fields=[
                'status', 'reject_reason', 'moderated_at',
                'moderated_by', 'updated_at',
            ])
            ReviewModerationLog.objects.create(
                review=review,
                action=ReviewModerationLog.ACTION_APPROVE,
                actor=request.user,
            )
        return Response({
            **ReviewAdminSerializer(review).data,
            'already_approved': already,
        })


class ReviewRejectView(_AdminOnly, APIView):
    VALID_REASONS = {code for code, _ in Review.REJECT_REASONS}

    @extend_schema(
        summary='Reject review with reason.',
        tags=['reviews'],
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            review = Review.objects.select_for_update().get(pk=pk)
        except Review.DoesNotExist:
            raise NotFound({
                'detail': 'Reseña no encontrada.',
                'codigo_error': 'RESENA_NO_ENCONTRADA',
            })

        reason = (request.data.get('reason') or '').strip()
        if reason not in self.VALID_REASONS:
            raise ValidationError({
                'detail': 'reason invalido.',
                'codigo_error': 'MOTIVO_INVALIDO',
                'allowed': sorted(self.VALID_REASONS),
            })

        if review.status == Review.STATUS_APPROVED:
            raise ValidationError({
                'detail': 'No se puede rechazar una reseña ya aprobada.',
                'codigo_error': 'RESENA_YA_APROBADA',
            })

        review.status = Review.STATUS_REJECTED
        review.reject_reason = reason
        review.moderated_at = timezone.now()
        review.moderated_by = request.user
        review.save(update_fields=[
            'status', 'reject_reason', 'moderated_at',
            'moderated_by', 'updated_at',
        ])
        ReviewModerationLog.objects.create(
            review=review,
            action=ReviewModerationLog.ACTION_REJECT,
            reason=reason,
            actor=request.user,
        )
        return Response(ReviewAdminSerializer(review).data)
