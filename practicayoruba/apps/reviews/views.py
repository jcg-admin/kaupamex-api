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
from rest_framework.throttling import ScopedRateThrottle
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

    def get_throttles(self):
        # UC-REV-02: throttle solo en POST para prevenir spam de reseñas.
        # H-CICLO29-02: sin throttle cualquier usuario autenticado podía
        # spamear el endpoint con distintos order_id.
        if self.request.method == 'POST':
            self.throttle_scope = 'review_create'
            return [ScopedRateThrottle()]
        return []

    @extend_schema(
        summary='List approved reviews for product (UC-REV-01).',
        tags=['reviews'],
        responses={200: ReviewPublicSerializer(many=True)},
    )
    def get(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise NotFound({
                'detail': 'Producto no encontrado.',
                'codigo_error': 'PRODUCT_NOT_FOUND',
            })

        rating_filter = request.query_params.get('rating')
        if rating_filter is not None:
            try:
                rating_int = int(rating_filter)
                if rating_int not in range(1, 6):
                    raise ValueError
            except ValueError:
                raise ValidationError({
                    'detail': 'rating debe ser un entero entre 1 y 5.',
                    'codigo_error': 'RATING_INVALID',
                })

        sort_by = request.query_params.get('sort', 'recent')

        approved = Review.objects.filter(
            product=product, status=Review.STATUS_APPROVED,
        ).select_related('user')

        if rating_filter is not None:
            approved = approved.filter(rating=rating_int)

        if sort_by == 'helpful':
            approved = approved.order_by('-helpful_count', '-created_at')
        else:
            approved = approved.order_by('-created_at')

        ratings_all = list(
            Review.objects.filter(product=product, status=Review.STATUS_APPROVED)
            .values_list('rating', flat=True)
        )
        total_all = len(ratings_all)
        avg = round(sum(ratings_all) / total_all, 2) if total_all else 0.0
        breakdown = Counter(ratings_all)
        rating_breakdown = {str(i): breakdown.get(i, 0) for i in range(1, 6)}

        # Pagination
        try:
            page_size = max(1, min(100, int(request.query_params.get('page_size', 10))))
            page_num = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            raise ValidationError({'detail': 'page_size y page deben ser enteros.',
                                   'codigo_error': 'INVALID_PAGINATION'})
        items = list(approved)
        count = len(items)
        pages = max(1, -(-count // page_size))  # ceil division
        start = (page_num - 1) * page_size
        end = start + page_size

        return Response({
            'product_id': product.id,
            'average_rating': avg,
            'total_reviews': total_all,
            'rating_breakdown': rating_breakdown,
            'count': count,
            'page': page_num,
            'pages': pages,
            'results': ReviewPublicSerializer(items[start:end], many=True).data,
        })

    @extend_schema(
        summary='Create review (UC-REV-02).',
        request=ReviewCreateSerializer,
        tags=['reviews'],
        responses={201: ReviewAdminSerializer, 400: None, 404: None},
    )
    @transaction.atomic
    def post(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise NotFound({
                'detail': 'Producto no encontrado.',
                'codigo_error': 'PRODUCT_NOT_FOUND',
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
                'codigo_error': 'ORDER_NOT_FOUND',
            })
        if order.user_id != request.user.id:
            raise PermissionDenied({
                'detail': 'No puedes reseñar productos que no compraste.',
                'codigo_error': 'PRODUCT_NOT_PURCHASED',
            })
        # UC-REV-01 PRE-01 + FR-REV-01.02 (T-118 D-01 CRITICA):
        # solo se permite resenar productos de ordenes ENTREGADAS. Antes
        # cualquier estado (PENDING/PROCESSING/SHIPPED) era aceptado =
        # vector reseñas pre-entrega.
        if order.status != Order.STATUS_DELIVERED:
            raise PermissionDenied({
                'detail': (
                    'Solo se pueden resenar productos de ordenes '
                    f'entregadas. Estado actual: {order.status}.'
                ),
                'codigo_error': 'ORDER_NOT_DELIVERED',
            })
        if not order.items.filter(product=product).exists():
            raise PermissionDenied({
                'detail': 'El producto no fue comprado en esa orden.',
                'codigo_error': 'PRODUCT_NOT_PURCHASED',
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
                'codigo_error': 'REVIEW_DUPLICATE',
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
        responses={200: ReviewAdminSerializer(many=True)},
    )
    def get(self, request):
        status_filter = request.query_params.get('status', Review.STATUS_PENDING)
        valid = {code for code, _ in Review.STATUSES}
        if status_filter not in valid:
            raise ValidationError({
                'detail': f'status invalido: {status_filter}.',
                'codigo_error': 'STATUS_INVALID',
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
        responses={200: ReviewAdminSerializer, 400: None, 404: None},
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            review = Review.objects.select_for_update().get(pk=pk)
        except Review.DoesNotExist:
            raise NotFound({
                'detail': 'Reseña no encontrada.',
                'codigo_error': 'REVIEW_NOT_FOUND',
            })

        already = review.status == Review.STATUS_APPROVED
        if review.status == Review.STATUS_REJECTED:
            raise ValidationError({
                'detail': 'No se puede aprobar una reseña ya rechazada.',
                'codigo_error': 'REVIEW_ALREADY_REJECTED',
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
        responses={200: ReviewAdminSerializer, 400: None, 404: None},
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            review = Review.objects.select_for_update().get(pk=pk)
        except Review.DoesNotExist:
            raise NotFound({
                'detail': 'Reseña no encontrada.',
                'codigo_error': 'REVIEW_NOT_FOUND',
            })

        reason = (request.data.get('reason') or '').strip()
        if reason not in self.VALID_REASONS:
            raise ValidationError({
                'detail': 'reason invalido.',
                'codigo_error': 'REASON_INVALID',
                'allowed': sorted(self.VALID_REASONS),
            })

        if review.status == Review.STATUS_APPROVED:
            raise ValidationError({
                'detail': 'No se puede rechazar una reseña ya aprobada.',
                'codigo_error': 'REVIEW_ALREADY_APPROVED',
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


class ReviewHelpfulVoteView(APIView):
    """POST /api/v1/products/<product_id>/reviews/<pk>/helpful/ — UC-REV-02."""
    permission_classes = [IsAuthenticated]

    def post(self, request, product_id, pk):
        from django.db.models import F
        from .models import ReviewHelpfulVote

        try:
            review = Review.objects.get(pk=pk, product_id=product_id, status=Review.STATUS_APPROVED)
        except Review.DoesNotExist:
            raise NotFound({'detail': 'Reseña no encontrada.', 'codigo_error': 'REVIEW_NOT_FOUND'})

        if review.user_id == request.user.id:
            raise ValidationError({
                'detail': 'No puedes votar tu propia reseña.',
                'codigo_error': 'CANNOT_VOTE_OWN_REVIEW',
            })

        if ReviewHelpfulVote.objects.filter(user=request.user, review=review).exists():
            raise ValidationError({
                'detail': 'Ya votaste esta reseña.',
                'codigo_error': 'VOTE_DUPLICATE',
            })

        with transaction.atomic():
            ReviewHelpfulVote.objects.create(user=request.user, review=review)
            Review.objects.filter(pk=review.pk).update(helpful_count=F('helpful_count') + 1, updated_at=timezone.now())

        review.refresh_from_db(fields=['helpful_count'])
        return Response({'helpful_count': review.helpful_count})
