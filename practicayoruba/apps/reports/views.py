"""
Views — apps.reports

Read-only admin aggregation endpoints under /api/v1/admin/reports/:
  GET /sales/?period=                 (UC-REP-01)
  GET /top-sellers/?period=&limit=    (UC-REP-02)
  GET /dashboard/                     (UC-REP-03)
  GET /customers-rfm/?period=&segment= (UC-REP-04)
  GET /<slug>/export/?format=csv|pdf   (UC-REP-05)

Identifiers + JSON keys in English (DEC-DOC-005).
"""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView


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
            from rest_framework import exceptions
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

from .aggregations import (
    build_dashboard_payload,
    build_rfm_payload,
    build_sales_payload,
    build_top_sellers_payload,
    parse_period,
)
from .exports import EXPORTERS


class _AdminMixin:
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = serializers.Serializer


class SalesReportView(_AdminMixin, APIView):
    @extend_schema(
        summary='Sales report (UC-REP-01)',
        parameters=[OpenApiParameter(name='period', required=False, type=str)],
        tags=['reports'],
    )
    def get(self, request):
        days = parse_period(request.query_params.get('period'))
        return Response(build_sales_payload(days))


class TopSellersReportView(_AdminMixin, APIView):
    @extend_schema(
        summary='Top sellers (UC-REP-02)',
        parameters=[
            OpenApiParameter(name='period', required=False, type=str),
            OpenApiParameter(name='limit', required=False, type=int),
        ],
        tags=['reports'],
    )
    def get(self, request):
        days = parse_period(request.query_params.get('period'))
        try:
            limit = int(request.query_params.get('limit', 10))
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 100))
        return Response(build_top_sellers_payload(days, limit))


class DashboardReportView(_AdminMixin, APIView):
    @extend_schema(summary='Dashboard snapshot (UC-REP-03)', tags=['reports'])
    def get(self, request):
        return Response(build_dashboard_payload())


class CustomersRFMReportView(_AdminMixin, APIView):
    @extend_schema(
        summary='Customers RFM (UC-REP-04)',
        parameters=[
            OpenApiParameter(name='period', required=False, type=str),
            OpenApiParameter(name='segment', required=False, type=str),
        ],
        tags=['reports'],
    )
    def get(self, request):
        days = parse_period(request.query_params.get('period'))
        segment = request.query_params.get('segment') or None
        return Response(build_rfm_payload(days, segment))


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
    )
    def get(self, request, slug):
        if slug not in EXPORTERS:
            return Response(
                {'error_code': 'REPORTE_NO_DISPONIBLE',
                 'detail': f'Unknown report: {slug}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        fmt = (request.query_params.get('format') or 'csv').lower()
        if fmt not in ('csv', 'pdf'):
            return Response(
                {'error_code': 'FORMATO_NO_SOPORTADO',
                 'detail': f'Unsupported format: {fmt}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        days = parse_period(request.query_params.get('period'))
        if slug == 'sales':
            payload = build_sales_payload(days)
        elif slug == 'top-sellers':
            try:
                limit = int(request.query_params.get('limit', 10))
            except (TypeError, ValueError):
                limit = 10
            payload = build_top_sellers_payload(days, max(1, min(limit, 100)))
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
                {'error_code': 'FORMATO_NO_SOPORTADO'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response
