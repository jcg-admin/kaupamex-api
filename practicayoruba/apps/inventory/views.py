"""Views — apps.inventory (Sprint 10)."""
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView

from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from apps.settings_app.models import SiteSettings

from .models import StockMovement, StockAlert
from .serializers import (
    StockDashboardSerializer, StockMovementSerializer,
    StockAlertSerializer, StockAdjustSerializer,
)
from .services import InventoryService, _get_stock_status


class InventoryDashboardView(APIView):
    """
    GET /api/v1/admin/inventory/
    Dashboard de inventario con estado NORMAL/BAJO/AGOTADO.
    Filtro opcional ?status=BAJO|AGOTADO|NORMAL.
    UC-INV-01 (FR-INV-01.02).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Dashboard de inventario',
        parameters=[
            OpenApiParameter('status', str,
                             description='Filtrar: NORMAL, BAJO, AGOTADO'),
        ],
        tags=['inventory'],
    )
    def get(self, request):
        threshold = SiteSettings.get_current().min_stock_threshold
        status_filter = request.query_params.get('status', '').upper()
        rows = []

        # Productos con variantes → iterar variantes
        for v in (ProductVariant.objects
                  .filter(product__is_active=True)
                  .select_related('product', 'option', 'option__variant_type')
                  .order_by('product__name', 'option__order')):
            st = _get_stock_status(v.stock, threshold)
            if status_filter and st != status_filter:
                continue
            rows.append({
                'product_id':    v.product.pk,
                'product_name':  v.product.name,
                'sku':           v.sku,
                'variant_id':    v.pk,
                'variant_label': v.option.label,
                'stock':         v.stock,
                'status':        st,
                'threshold':     threshold,
            })

        # Productos sin variantes → usar Product.stock
        products_with_variants = set(
            ProductVariant.objects
            .filter(is_active=True)
            .values_list('product_id', flat=True)
        )
        for p in (Product.objects
                  .filter(is_active=True)
                  .exclude(pk__in=products_with_variants)
                  .order_by('name')):
            st = _get_stock_status(p.stock, threshold)
            if status_filter and st != status_filter:
                continue
            rows.append({
                'product_id':    p.pk,
                'product_name':  p.name,
                'sku':           p.sku,
                'variant_id':    None,
                'variant_label': None,
                'stock':         p.stock,
                'status':        st,
                'threshold':     threshold,
            })

        return Response({
            'threshold': threshold,
            'count': len(rows),
            'results': rows,
        })


class StockAdjustView(APIView):
    """
    POST /api/v1/admin/inventory/<product_pk>/adjust/
    Ajuste manual de stock de un producto (sin variante). UC-INV-04.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Ajuste manual de stock (producto sin variante)',
        tags=['inventory'],
    )
    def post(self, request, product_pk):
        from django.shortcuts import get_object_or_404
        product = get_object_or_404(Product, pk=product_pk, is_active=True)
        s = StockAdjustSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        mov = InventoryService.adjust(
            product=product, variant=None,
            new_stock=s.validated_data['new_stock'],
            notes=s.validated_data.get('notes', ''),
            created_by=request.user,
        )
        return Response(StockMovementSerializer(mov).data, status=201)


class VariantStockAdjustView(APIView):
    """
    POST /api/v1/admin/inventory/variants/<variant_pk>/adjust/
    Ajuste manual de stock de una variante. UC-INV-04.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Ajuste manual de stock (variante)',
        tags=['inventory'],
    )
    def post(self, request, variant_pk):
        from django.shortcuts import get_object_or_404
        variant = get_object_or_404(ProductVariant, pk=variant_pk, is_active=True)
        s = StockAdjustSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        mov = InventoryService.adjust(
            product=variant.product, variant=variant,
            new_stock=s.validated_data['new_stock'],
            notes=s.validated_data.get('notes', ''),
            created_by=request.user,
        )
        return Response(StockMovementSerializer(mov).data, status=201)


class StockAlertListView(ListAPIView):
    """GET /api/v1/admin/inventory/alerts/ — alertas pendientes. UC-INV-01."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = StockAlertSerializer

    def get_queryset(self):
        return StockAlert.objects.filter(resolved=False).select_related(
            'product', 'variant', 'variant__option'
        )
