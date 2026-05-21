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
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Product, ProductDiscount
from .product_discount_serializers import ProductDiscountCreateSerializer, ProductDiscountSerializer, ProductDiscountUpdateSerializer



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
        summary='List product discounts (UC-DASH-01)',
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
        qs = ProductDiscount.objects.select_related('product').all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = _filter_by_status(qs, status_filter.upper())
        data = ProductDiscountSerializer(qs, many=True).data
        return Response({'results': data})

    @extend_schema(
        summary='Create product discount (UC-DASH-02)',
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

        now = timezone.now()
        active_qs = ProductDiscount.objects.filter(
            product=product, is_active=True, valid_from__lte=now,
        ).filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now))
        if active_qs.exists():
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
        summary='Edit product discount (UC-DASH-03)',
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

        for field, value in serializer.validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return Response(ProductDiscountSerializer(instance).data)


class ProductDiscountDeactivateView(APIView):
    """POST /api/v1/admin/product-discounts/<id>/deactivate/."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = ProductDiscountSerializer

    @extend_schema(
        summary='Deactivate product discount (UC-DASH-04)',
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
