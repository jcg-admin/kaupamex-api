"""
Views — apps.reports

Read-only admin aggregation endpoints under /api/v1/admin/reports/:
  GET /sales/?period=                         (UC-REP-01)
  GET /top-sellers/?period=&limit=&sort=      (UC-REP-02)
  GET /dashboard/                             (UC-REP-03)
  GET /customers-rfm/?period=&segment=        (UC-REP-04)
  GET /<slug>/export/?format=csv&period=...   (UC-REP-05)

SP-backed endpoints (implementar-endpoints-db-rpt sucesora):
  GET /catalog-by-category/   (UC-DB-RPT-01, sp_rpt_catalog_by_category)
  GET /low-stock/             (UC-DB-RPT-02, sp_rpt_low_stock)
  GET /catalog-summary/       (UC-DB-RPT-03, sp_rpt_catalog_summary)

Identifiers + JSON keys in English (DEC-DOC-005).
"""
from django.core.cache import cache
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status, exceptions
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from .aggregations import (
    build_dashboard_payload, build_rfm_payload, build_sales_payload,
    build_top_sellers_payload, count_export_rows, parse_period,
)
from .exports import EXPORTERS
from .sp_helpers import call_sp

# D-19: async export for >5000 rows not yet implemented (DEC-REP-01).
_EXPORT_ASYNC_THRESHOLD = 5000


def _sp_response(sp_name: str) -> Response:
    """DEC-DBR-04 shape: {generated_at, count, results} para los 3
    endpoints SP-backed."""
    rows = call_sp(sp_name)
    return Response({
        'generated_at': timezone.now().isoformat(),
        'count': len(rows),
        'results': rows,
    })


class _PassthroughNegotiator(DefaultContentNegotiation):
    """
    Negotiator that ignores the ?format= query param. The export view
    handles format itself; we don't want DRF filtering renderers (and
    raising Http404) based on a query string the contract owns.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        # Always return the first renderer with its media type, skipping
        # DRF's Accept-header / URL_FORMAT_OVERRIDE filtering entirely.
        if not renderers:
            raise exceptions.NotAcceptable()
        return renderers[0], renderers[0].media_type


class _CSVRenderer(BaseRenderer):
    media_type = 'text/csv'
    format = 'csv'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data if isinstance(data, (bytes, str)) else str(data)


class _PDFRenderer(BaseRenderer):
    media_type = 'application/pdf'
    format = 'pdf'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data if isinstance(data, (bytes, str)) else str(data)



class _AdminMixin:
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = serializers.Serializer


class SalesReportView(_AdminMixin, APIView):
    _CACHE_TTL = 300  # 5 min — UC-REP-01

    @extend_schema(
        summary='Sales report (UC-REP-01)',
        parameters=[OpenApiParameter(name='period', required=False, type=str)],
        tags=['reports'],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        days = parse_period(request.query_params.get('period'))
        key = f'reports:sales:{days}'
        payload = cache.get(key)
        if payload is None:
            payload = build_sales_payload(days)
            cache.set(key, payload, self._CACHE_TTL)
        return Response(payload)


class TopSellersReportView(_AdminMixin, APIView):
    _CACHE_TTL = 600  # 10 min — UC-REP-02

    @extend_schema(
        summary='Top sellers (UC-REP-02)',
        parameters=[
            OpenApiParameter(name='period', required=False, type=str),
            OpenApiParameter(name='limit', required=False, type=int),
            OpenApiParameter(
                name='sort', required=False, type=str,
                description='UNIDADES|INGRESOS (default UNIDADES)',
            ),
        ],
        tags=['reports'],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        days = parse_period(request.query_params.get('period'))
        try:
            limit = int(request.query_params.get('limit', 10))
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 50))  # D-08: UC-REP-02 max 50
        sort_by = (request.query_params.get('sort') or 'UNIDADES').upper()
        if sort_by not in ('UNIDADES', 'INGRESOS'):
            sort_by = 'UNIDADES'
        key = f'reports:top-sellers:{days}:{limit}:{sort_by}'
        payload = cache.get(key)
        if payload is None:
            payload = build_top_sellers_payload(days, limit, sort_by=sort_by)
            cache.set(key, payload, self._CACHE_TTL)
        return Response(payload)


class DashboardReportView(_AdminMixin, APIView):
    _CACHE_TTL = 30  # 30 s — UC-REP-03

    @extend_schema(summary='Dashboard snapshot (UC-REP-03)', tags=['reports'],
                   responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        key = 'reports:dashboard'
        payload = cache.get(key)
        if payload is None:
            payload = build_dashboard_payload()
            cache.set(key, payload, self._CACHE_TTL)
        return Response(payload)


class CustomersRFMReportView(_AdminMixin, APIView):
    _CACHE_TTL = 3600  # 1 h — UC-REP-04

    @extend_schema(
        summary='Customers RFM (UC-REP-04)',
        parameters=[
            OpenApiParameter(name='period', required=False, type=str),
            OpenApiParameter(
                name='segment', required=False, type=str,
                description='CHAMPIONS|LOYAL|RECENT|AT_RISK|OCCASIONAL',
            ),
        ],
        tags=['reports'],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        days = parse_period(request.query_params.get('period'))
        segment = request.query_params.get('segment') or None
        seg_key = (segment or '').upper()
        key = f'reports:rfm:{days}:{seg_key}'
        payload = cache.get(key)
        if payload is None:
            payload = build_rfm_payload(days, segment)
            cache.set(key, payload, self._CACHE_TTL)
        return Response(payload)


class ReportExportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = serializers.Serializer
    # DRF normally interprets ?format= as a renderer selector and raises
    # Http404 if no renderer matches. The export contract uses ?format=
    # for the output type (csv|pdf) instead, so we install a passthrough
    # negotiator that ignores the query param. The view itself returns
    # a streaming HTTP response and handles format validation explicitly.
    content_negotiation_class = _PassthroughNegotiator
    renderer_classes = [JSONRenderer, _CSVRenderer, _PDFRenderer]

    @extend_schema(
        summary='Export a report (UC-REP-05)',
        parameters=[
            OpenApiParameter(name='format', required=False, type=str,
                             description='csv|pdf (default csv)'),
            OpenApiParameter(name='period', required=False, type=str),
            OpenApiParameter(name='limit', required=False, type=int),
            OpenApiParameter(name='segment', required=False, type=str),
        ],
        tags=['reports'],
        responses={
            200: OpenApiResponse(description='CSV file.', response=OpenApiTypes.BINARY),
            400: None,
            404: None,
            501: None,
        },
    )
    def get(self, request, slug):
        if slug not in EXPORTERS:
            return Response(
                {'error_code': 'REPORT_UNAVAILABLE',
                 'detail': f'Unknown report: {slug}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        fmt = (request.query_params.get('format') or 'csv').lower()
        if fmt not in ('csv', 'pdf'):
            return Response(
                {'error_code': 'FORMAT_NOT_SUPPORTED',
                 'detail': f'Unsupported format: {fmt}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # D-20: PDF export not yet implemented (DEC-REP-01).
        if fmt == 'pdf':
            return Response(
                {'error_code': 'ASYNC_EXPORT_NOT_AVAILABLE',
                 'detail': 'PDF export is not yet implemented.'},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        days = parse_period(request.query_params.get('period'))

        # D-19: async export for large datasets not yet implemented (DEC-REP-01).
        row_count = count_export_rows(slug, days)
        if row_count > _EXPORT_ASYNC_THRESHOLD:
            return Response(
                {
                    'error_code': 'ASYNC_EXPORT_NOT_AVAILABLE',
                    'detail': (
                        f'Export has {row_count} rows which exceeds the '
                        f'{_EXPORT_ASYNC_THRESHOLD}-row limit. '
                        'Async export is not yet implemented.'
                    ),
                },
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        if slug == 'sales':
            payload = build_sales_payload(days)
        elif slug == 'top-sellers':
            try:
                limit = int(request.query_params.get('limit', 10))
            except (TypeError, ValueError):
                limit = 10
            sort_by = (request.query_params.get('sort') or 'UNIDADES').upper()
            if sort_by not in ('UNIDADES', 'INGRESOS'):
                sort_by = 'UNIDADES'
            payload = build_top_sellers_payload(days, max(1, min(limit, 50)), sort_by=sort_by)
        elif slug == 'customers-rfm':
            payload = build_rfm_payload(
                days, request.query_params.get('segment') or None,
            )
        elif slug == 'dashboard':
            payload = build_dashboard_payload()
        else:
            payload = {}

        exporter = EXPORTERS[slug]
        response = exporter(payload, fmt)
        if response is None:
            return Response(
                {'error_code': 'FORMAT_NOT_SUPPORTED'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response


# ─── SP-backed endpoints — implementar-endpoints-db-rpt sucesora ────────


class CatalogByCategoryReportView(_AdminMixin, APIView):
    """UC-DB-RPT-01 — invoca sp_rpt_catalog_by_category (D-26 T-114)."""

    @extend_schema(
        summary='Catalog by category report (UC-DB-RPT-01)',
        tags=['reports'],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        return _sp_response('sp_rpt_catalog_by_category')


class LowStockReportView(_AdminMixin, APIView):
    """UC-DB-RPT-02 — invoca sp_rpt_low_stock (D-27 T-114)."""

    @extend_schema(
        summary='Low stock report (UC-DB-RPT-02)',
        tags=['reports'],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        return _sp_response('sp_rpt_low_stock')


class CatalogSummaryReportView(_AdminMixin, APIView):
    """UC-DB-RPT-03 — invoca sp_rpt_catalog_summary (D-28 T-114)."""

    @extend_schema(
        summary='Catalog summary report (UC-DB-RPT-03)',
        tags=['reports'],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        return _sp_response('sp_rpt_catalog_summary')
