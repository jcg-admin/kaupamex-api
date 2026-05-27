"""
Views — ProductDiscount (UC-DASH-01..04).

Endpoints under /api/v1/admin/product-discounts/:
  GET    /                   list (optional ?status=CURRENT|FUTURE|EXPIRED)
  POST   /                   create
  PATCH  /<id>/              partial update (product_id immutable)
  POST   /<id>/deactivate/   soft deactivate

DEC-DOC-005: English identifiers and English JSON keys.
"""
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Product, ProductDiscount
from .product_discount_serializers import ProductDiscountCreateSerializer, ProductDiscountSerializer, ProductDiscountUpdateSerializer


class ProductDiscountPagination(PageNumberPagination):
    page_size             = 25
    page_size_query_param = 'page_size'
    max_page_size         = 100



def _filter_by_status(qs, status_filter):
    now = timezone.now()
    if status_filter == 'CURRENT':
        return qs.filter(
            is_active=True,
            valid_from__lte=now,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now))
    if status_filter == 'FUTURE':
        return qs.filter(is_active=True, valid_from__gt=now)
    if status_filter == 'EXPIRED':
        return qs.filter(
            is_active=True,
            valid_until__isnull=False,
            valid_until__lt=now,
        )
    return qs


class ProductDiscountListCreateView(APIView):
    """GET and POST /api/v1/admin/product-discounts/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='List product discounts (UC-DASH-04)',
        parameters=[
            OpenApiParameter(
                name='status', required=False, type=str,
                description='Optional filter: CURRENT|FUTURE|EXPIRED',
            ),
        ],
        responses=ProductDiscountSerializer(many=True),
        tags=['product-discounts'],
    )
    def get(self, request):
        qs = ProductDiscount.objects.select_related('product').all().order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = _filter_by_status(qs, status_filter.upper())
        paginator = ProductDiscountPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(ProductDiscountSerializer(page, many=True).data)
        return Response({'results': ProductDiscountSerializer(qs, many=True).data})

    @extend_schema(
        summary='Create product discount (UC-DASH-01)',
        request=ProductDiscountCreateSerializer,
        responses={201: ProductDiscountSerializer},
        tags=['product-discounts'],
    )
    def post(self, request):
        serializer = ProductDiscountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            product = Product.objects.get(pk=data['product_id'])
        except Product.DoesNotExist:
            return Response(
                {'error_code': 'PRODUCT_UNAVAILABLE',
                 'detail': 'Product not found.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if not product.is_active:
            return Response(
                {'error_code': 'PRODUCT_UNAVAILABLE',
                 'detail': 'Product is inactive.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Reject if a new discount's date range overlaps any existing
        # active (or future) discount for the same product.
        # The check covers both currently-active and future discounts so
        # two FUTURE records cannot be stacked and simultaneously become
        # CURRENT when their valid_from arrives.
        new_from  = data['valid_from']
        new_until = data.get('valid_until')  # None means open-ended

        overlap_qs = ProductDiscount.objects.filter(
            product=product, is_active=True,
        ).filter(
            # Existing discount has not yet expired (or is open-ended)
            Q(valid_until__isnull=True) | Q(valid_until__gt=new_from),
        )
        if new_until is not None:
            # New discount ends at some point — only overlaps exist that
            # start before new_until.
            overlap_qs = overlap_qs.filter(valid_from__lt=new_until)
        if overlap_qs.exists():
            return Response(
                {'error_code': 'ACTIVE_DISCOUNT_EXISTS',
                 'detail': 'An active discount already exists for this product.'},
                status=status.HTTP_409_CONFLICT,
            )

        discount = ProductDiscount.objects.create(
            product=product,
            discount_pct=data['discount_pct'],
            valid_from=data['valid_from'],
            valid_until=data.get('valid_until'),
            is_active=True,
            created_by=request.user,
        )
        return Response(
            ProductDiscountSerializer(discount).data,
            status=status.HTTP_201_CREATED,
        )


class ProductDiscountDetailView(APIView):
    """PATCH /api/v1/admin/product-discounts/<id>/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_or_404(self, pk):
        try:
            return ProductDiscount.objects.select_related('product').get(pk=pk)
        except ProductDiscount.DoesNotExist:
            return None

    @extend_schema(
        summary='Edit product discount (UC-DASH-02)',
        request=ProductDiscountUpdateSerializer,
        responses=ProductDiscountSerializer,
        tags=['product-discounts'],
    )
    def patch(self, request, pk):
        instance = self._get_or_404(pk)
        if instance is None:
            return Response(
                {'error_code': 'DISCOUNT_NOT_APPLICABLE',
                 'detail': 'Discount not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # product_id is immutable — ignore if sent
        serializer = ProductDiscountUpdateSerializer(
            instance=instance, data=request.data, partial=True,
        )
        if not serializer.is_valid():
            # If the date-range error code is present, surface as 422
            errors = serializer.errors
            if any('INVALID_DATE_RANGE' in str(v) for v in errors.values()):
                return Response(
                    {'error_code': 'INVALID_DATE_RANGE',
                     'detail': 'Invalid date range.'},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # Overlap check: only run when dates are being changed.
        if 'valid_from' in serializer.validated_data or 'valid_until' in serializer.validated_data:
            upd_from  = serializer.validated_data.get('valid_from', instance.valid_from)
            upd_until = serializer.validated_data.get('valid_until', instance.valid_until)
            overlap_qs = ProductDiscount.objects.filter(
                product=instance.product, is_active=True,
            ).exclude(pk=instance.pk).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gt=upd_from),
            )
            if upd_until is not None:
                overlap_qs = overlap_qs.filter(valid_from__lt=upd_until)
            if overlap_qs.exists():
                return Response(
                    {'error_code': 'ACTIVE_DISCOUNT_EXISTS',
                     'detail': 'An active discount already exists for this product.'},
                    status=status.HTTP_409_CONFLICT,
                )

        changed_fields = list(serializer.validated_data.keys())
        for field, value in serializer.validated_data.items():
            setattr(instance, field, value)
        instance.save(update_fields=changed_fields + ['updated_at'])
        return Response(ProductDiscountSerializer(instance).data)


class ProductDiscountDeactivateView(APIView):
    """POST /api/v1/admin/product-discounts/<id>/deactivate/."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = ProductDiscountSerializer

    @extend_schema(
        summary='Deactivate product discount (UC-DASH-03)',
        responses=ProductDiscountSerializer,
        tags=['product-discounts'],
    )
    def post(self, request, pk):
        try:
            instance = ProductDiscount.objects.select_related('product').get(pk=pk)
        except ProductDiscount.DoesNotExist:
            return Response(
                {'error_code': 'DISCOUNT_NOT_APPLICABLE',
                 'detail': 'Discount not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not instance.is_active:
            return Response(
                {'error_code': 'DISCOUNT_ALREADY_INACTIVE',
                 'detail': 'Discount is already inactive.'},
                status=status.HTTP_409_CONFLICT,
            )
        instance.is_active = False
        instance.deactivated_at = timezone.now()
        instance.deactivated_by = request.user
        instance.save(update_fields=[
            'is_active', 'deactivated_at', 'deactivated_by', 'updated_at',
        ])
        return Response(ProductDiscountSerializer(instance).data)
