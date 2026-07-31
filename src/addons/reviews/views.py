"""
Views — addons.reviews (P-14 / UC-REV-01..03).

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
from addons.sale.models import SaleOrder
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from addons.authz.permissions import HasCapability
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from addons.catalogue.models import Product
from addons.sale.status_projection import (
    STATUS_DELIVERED,
    order_status,
)
from addons.rating.models import Review, ReviewHelpfulVote, ReviewImage, ReviewModerationLog
from config.schema import error_response
from .serializers import (
    ReviewAdminSerializer, ReviewCreateSerializer, ReviewImageSerializer,
    ReviewPublicSerializer, ReviewUpdateSerializer,
)





# =============================================================================
# Public — list + create per product
# =============================================================================

class ProductReviewsView(APIView):
    """GET (public) / POST (auth) /api/v1/products/<product_id>/reviews/."""

    serializer_class = ReviewPublicSerializer
    # Enforcement (ADR-020, DEC-ENF-01): crear reseña es una acción propia del
    # comprador → exige account.reviews. El GET de listado sigue público.
    required_capability = 'account.reviews'

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), HasCapability()]
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
        ).select_related('user').prefetch_related('images')

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
        # H-CICLO117-01: usar count() + slicing en DB en lugar de list()
        # completo. El list() anterior cargaba TODAS las reseñas aprobadas en
        # memoria antes de paginear; en productos con miles de reseñas esto
        # producía consumo O(N) por request. El fix evalúa solo la página
        # solicitada directamente en la BD.
        try:
            page_size = max(1, min(100, int(request.query_params.get('page_size', 10))))
            page_num = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            raise ValidationError({'detail': 'page_size y page deben ser enteros.',
                                   'codigo_error': 'INVALID_PAGINATION'})
        count = approved.count()
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
            'results': ReviewPublicSerializer(approved[start:end], many=True).data,
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

        # SaleOrder ownership check + product purchased.
        try:
            order = SaleOrder.objects.get(pk=data['order_id'])
        except SaleOrder.DoesNotExist:
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
        current_status = order_status(order)  # V5c-2: derivado de sale
        if current_status != STATUS_DELIVERED:
            raise PermissionDenied({
                'detail': (
                    'Solo se pueden resenar productos de ordenes '
                    f'entregadas. Estado actual: {current_status}.'
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
                sale_order=order,
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

        # Re-fetch con select_related para evitar N+1: ReviewAdminSerializer
        # accede a review.user, review.product y —tras I2— review.sale_order
        # (la identidad se lee de la canónica).
        review = Review.objects.select_related('user', 'product', 'sale_order').get(pk=review.pk)

        return Response(
            ReviewAdminSerializer(review).data,
            status=status.HTTP_201_CREATED,
        )


# =============================================================================
# Buyer — edit own pending review (UC-REV-01 Alt B)
# =============================================================================

class ReviewUpdateView(APIView):
    """
    PATCH /api/v1/products/<product_id>/reviews/<pk>/edit/

    UC-REV-01 Alt B: buyer edits their own review while it is still
    PENDING_MODERATION. Fields: rating, title, body (all optional).
    Returns 403 if caller does not own the review; 400 if the review
    has already been approved or rejected.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.reviews'

    @extend_schema(
        summary='[DEPRECATED → /api/v2/products/<id>/reviews/<pk>/] Editar reseña propia pendiente (UC-REV-01 Alt B)',
        deprecated=True, tags=['reviews'],
        request=ReviewUpdateSerializer,
        responses={200: ReviewAdminSerializer,
                   400: error_response('Reseña no editable'),
                   403: error_response('No eres el dueño de la reseña'),
                   404: error_response('Reseña no encontrada')})
    def patch(self, request, product_id, pk):
        try:
            review = Review.objects.select_related('user', 'product', 'sale_order').get(
                pk=pk, product_id=product_id,
            )
        except Review.DoesNotExist:
            raise NotFound({
                'detail': 'Reseña no encontrada.',
                'codigo_error': 'REVIEW_NOT_FOUND',
            })

        if review.user_id != request.user.id:
            raise PermissionDenied({'codigo_error': 'REVIEW_NOT_OWNER'})

        if review.status != Review.STATUS_PENDING:
            raise ValidationError({'codigo_error': 'REVIEW_NOT_EDITABLE'})

        ser = ReviewUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        review = ser.update(review, ser.validated_data)
        return Response(ReviewAdminSerializer(review).data)


# =============================================================================
# Buyer — add photo to own review (UC-REV-02 cap6)
# =============================================================================

class ReviewImageCreateView(generics.CreateAPIView):
    """UC-REV-02 cap6 — author adds photo to own review (max 3)."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.reviews'
    serializer_class   = ReviewImageSerializer
    parser_classes     = [MultiPartParser, FormParser]

    def get_review(self):
        review = get_object_or_404(
            Review,
            pk=self.kwargs['pk'],
            product_id=self.kwargs['product_id'],
        )
        if review.user_id != self.request.user.id:
            raise PermissionDenied({'codigo_error': 'REVIEW_NOT_OWNER'})
        return review

    def perform_create(self, serializer):
        review = self.get_review()
        if review.images.count() >= 3:
            raise ValidationError({'codigo_error': 'REVIEW_MAX_IMAGES_REACHED'})
        serializer.save(review=review)


# =============================================================================
# Admin — moderation queue + approve / reject
# =============================================================================

class _AdminReviewPagination(PageNumberPagination):
    """H-CICLO90-01: paginar cola de moderacion de resenas para evitar OOM."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class _AdminOnly:
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'moderation.edit'
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
            .select_related('user', 'product', 'sale_order')
            .order_by('created_at')  # FIFO
        )
        # H-CICLO90-01: paginar para evitar OOM en tiendas con cola de
        # moderacion grande. Patron identico a AdminQuestionsListView
        # (H-CICLO84-02) y AdminSupportTicketListView (H-CICLO89-01).
        paginator = _AdminReviewPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                ReviewAdminSerializer(page, many=True).data
            )
        return Response({'results': ReviewAdminSerializer(qs, many=True).data})


class ReviewApproveView(_AdminOnly, APIView):
    @extend_schema(
        summary='[DEPRECATED → PATCH /api/v2/admin/reviews/<pk>/status/] Approve review (idempotent).',
        deprecated=True,
        tags=['reviews'],
        responses={200: ReviewAdminSerializer, 400: None, 404: None},
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            review = Review.objects.select_related(
                'user', 'product', 'order'
            ).select_for_update().get(pk=pk)
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
        summary='[DEPRECATED → PATCH /api/v2/admin/reviews/<pk>/status/] Reject review with reason.',
        deprecated=True,
        tags=['reviews'],
        responses={200: ReviewAdminSerializer, 400: None, 404: None},
    )
    @transaction.atomic
    def post(self, request, pk):
        try:
            review = Review.objects.select_related(
                'user', 'product', 'order'
            ).select_for_update().get(pk=pk)
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
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.reviews'

    @extend_schema(
        summary='Votar reseña como útil (UC-REV-02)', tags=['reviews'],
        request=None,
        responses={200: inline_serializer(
            'ReviewHelpfulVoteResponse',
            {'helpful_count': serializers.IntegerField()}),
            400: error_response('Voto duplicado o voto sobre reseña propia'),
            404: error_response('Reseña no encontrada')})
    def post(self, request, product_id, pk):
        try:
            review = Review.objects.get(pk=pk, product_id=product_id, status=Review.STATUS_APPROVED)
        except Review.DoesNotExist:
            raise NotFound({'detail': 'Reseña no encontrada.', 'codigo_error': 'REVIEW_NOT_FOUND'})

        if review.user_id == request.user.id:
            raise ValidationError({
                'detail': 'No puedes votar tu propia reseña.',
                'codigo_error': 'CANNOT_VOTE_OWN_REVIEW',
            })

        # H-CICLO111-03: mover el chequeo de duplicado DENTRO del atomic y
        # capturar IntegrityError como defensa en profundidad. Sin esto, dos
        # requests concurrentes pueden pasar el .exists() simultáneamente y
        # el segundo create() lanza IntegrityError no capturado (500). El
        # unique_together de ReviewHelpfulVote garantiza integridad en BD,
        # pero el manejo de error faltaba en la capa de vista.
        try:
            with transaction.atomic():
                if ReviewHelpfulVote.objects.filter(user=request.user, review=review).exists():
                    raise ValidationError({
                        'detail': 'Ya votaste esta reseña.',
                        'codigo_error': 'VOTE_DUPLICATE',
                    })
                ReviewHelpfulVote.objects.create(user=request.user, review=review)
                Review.objects.filter(pk=review.pk).update(helpful_count=F('helpful_count') + 1, updated_at=timezone.now())
        except IntegrityError:
            raise ValidationError({
                'detail': 'Ya votaste esta reseña.',
                'codigo_error': 'VOTE_DUPLICATE',
            })

        review.refresh_from_db(fields=['helpful_count'])
        return Response({'helpful_count': review.helpful_count})


class ReviewStatusV2View(APIView):
    """PATCH /api/v2/admin/reviews/<pk>/status/ — Tier B."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'moderation.edit'

    def patch(self, request, pk):
        action = (request.data.get('action') or '').strip()
        if action == 'approve':
            return ReviewApproveView().post(request, pk)
        if action == 'reject':
            return ReviewRejectView().post(request, pk)
        return Response(
            {
                'detail': "action debe ser 'approve' o 'reject'.",
                'codigo_error': 'INVALID_ACTION',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
