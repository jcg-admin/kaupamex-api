"""
Views — addons.reports

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
import logging
import os
import tempfile
import threading

from datetime import timedelta

from django.core import signing
from django.core.cache import cache
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status, exceptions
from rest_framework.permissions import IsAuthenticated
from addons.authz.permissions import HasCapability
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from .aggregations import (
    build_dashboard_payload, build_rfm_payload, build_sales_payload,
    build_top_sellers_payload, count_export_rows, parse_period,
)
from .exports import EXPORTERS
from addons.base.models import ExportJob
from .pdf_report import PdfGenerationError
from .serializers import ExportJobSerializer
from .sp_helpers import call_sp

logger = logging.getLogger('apps')

# D-19: rows>5000 take the async branch (DEC-REP-01). The project has no
# Celery/Redis, so the long export runs in a threading.Thread worker (same
# no-Celery pattern as addons.auto_backup) and the file is fetched later via a
# signed, time-limited download URL.
_EXPORT_ASYNC_THRESHOLD = 5000

# Signed download links are valid for ~1h (FR-RPT-04.02 esc 2-4).
_DOWNLOAD_MAX_AGE_SECONDS = 3600
_DOWNLOAD_SALT = 'addons.reports.export-download'

_EXPORT_CONTENT_TYPES = {
    'csv': 'text/csv',
    'xlsx': ('application/vnd.openxmlformats-officedocument'
             '.spreadsheetml.sheet'),
    'pdf': 'application/pdf',
}


def _sign_job_token(job_pk: int) -> str:
    """Return a signed, timestamped token that authorizes downloading a job."""
    return signing.TimestampSigner(salt=_DOWNLOAD_SALT).sign(str(job_pk))


def _unsign_job_token(token: str):
    """Validate a download token. Return the job pk or None if invalid/expired."""
    try:
        raw = signing.TimestampSigner(salt=_DOWNLOAD_SALT).unsign(
            token, max_age=_DOWNLOAD_MAX_AGE_SECONDS,
        )
        return int(raw)
    except (signing.BadSignature, signing.SignatureExpired, ValueError):
        return None


def _build_export_payload(slug: str, params: dict):
    """Reproduce the synchronous serialization for a given report slug."""
    days = params.get('days', 30)
    if slug == 'sales':
        return build_sales_payload(days)
    if slug == 'top-sellers':
        limit = max(1, min(int(params.get('limit', 10)), 50))
        sort_by = (params.get('sort') or 'UNIDADES').upper()
        if sort_by not in ('UNIDADES', 'INGRESOS'):
            sort_by = 'UNIDADES'
        return build_top_sellers_payload(days, limit, sort_by=sort_by)
    if slug == 'customers-rfm':
        return build_rfm_payload(days, params.get('segment') or None)
    if slug == 'dashboard':
        return build_dashboard_payload()
    return {}


def _run_export_job(job_pk: int) -> None:
    """Worker — generate the export file and update the ExportJob record.

    Reuses the synchronous CSV/XLSX/PDF code paths (EXPORTERS) and persists
    the rendered bytes to a temp file so the admin can download it later.
    Runnable synchronously for tests (mirrors addons.auto_backup._run_backup).
    """
    try:
        ExportJob.objects.filter(pk=job_pk).update(
            status=ExportJob.STATUS_RUNNING,
        )
        job = ExportJob.objects.get(pk=job_pk)
        slug = job.params.get('slug')
        fmt = (job.params.get('format') or 'csv').lower()
        payload = _build_export_payload(slug, job.params)
        exporter = EXPORTERS[slug]
        response = exporter(payload, fmt)
        if response is None:
            raise ValueError(f'Unsupported export format: {fmt}')
        # Both StreamingHttpResponse and HttpResponse expose their bytes;
        # join streaming chunks to a single bytes blob.
        if getattr(response, 'streaming', False):
            content = b''.join(
                c if isinstance(c, bytes) else c.encode('utf-8')
                for c in response.streaming_content
            )
        else:
            content = response.content
        fd, path = tempfile.mkstemp(prefix=f'export-{slug}-', suffix=f'.{fmt}')
        with os.fdopen(fd, 'wb') as fh:
            fh.write(content)
        ExportJob.objects.filter(pk=job_pk).update(
            status=ExportJob.STATUS_DONE,
            file_path=path,
            expires_at=timezone.now() + timedelta(
                seconds=_DOWNLOAD_MAX_AGE_SECONDS,
            ),
        )
        logger.info('ExportJob #%d completado: %s', job_pk, path)
    except Exception as exc:
        ExportJob.objects.filter(pk=job_pk).update(
            status=ExportJob.STATUS_ERROR,
            error_detail=str(exc)[:1000],
        )
        logger.exception('ExportJob #%d falló.', job_pk)


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


class _XLSXRenderer(BaseRenderer):
    media_type = (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    format = 'xlsx'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data if isinstance(data, (bytes, str)) else str(data)



class _AdminMixin:
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'reports.view'
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
    # Generar un export es más sensible que ver el reporte en pantalla:
    # exige la capacidad dedicada reports.export (DEC-ENF-01), no reports.view.
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'reports.export'
    serializer_class = serializers.Serializer
    # DRF normally interprets ?format= as a renderer selector and raises
    # Http404 if no renderer matches. The export contract uses ?format=
    # for the output type (csv|pdf) instead, so we install a passthrough
    # negotiator that ignores the query param. The view itself returns
    # a streaming HTTP response and handles format validation explicitly.
    content_negotiation_class = _PassthroughNegotiator
    renderer_classes = [JSONRenderer, _CSVRenderer, _XLSXRenderer, _PDFRenderer]

    @extend_schema(
        summary='Export a report (UC-REP-05)',
        parameters=[
            OpenApiParameter(name='format', required=False, type=str,
                             description='csv|xlsx|pdf (default csv)'),
            OpenApiParameter(name='period', required=False, type=str),
            OpenApiParameter(name='limit', required=False, type=int),
            OpenApiParameter(name='segment', required=False, type=str),
        ],
        tags=['reports'],
        responses={
            200: OpenApiResponse(description='CSV/XLSX/PDF file.',
                                 response=OpenApiTypes.BINARY),
            202: OpenApiResponse(
                description='Async export enqueued (rows>5000); poll the '
                            'job status endpoint for the download URL.',
                response=OpenApiTypes.OBJECT),
            400: None,
            404: None,
        },
    )
    def get(self, request, slug):
        if slug not in EXPORTERS:
            return Response(
                {'codigo_error': 'REPORT_UNAVAILABLE',
                 'detail': f'Unknown report: {slug}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        fmt = (request.query_params.get('format') or 'csv').lower()
        if fmt not in ('csv', 'xlsx', 'pdf'):
            return Response(
                {'codigo_error': 'FORMAT_NOT_SUPPORTED',
                 'detail': f'Unsupported format: {fmt}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        days = parse_period(request.query_params.get('period'))

        # D-19: rows>5000 take the async branch (DEC-REP-01). No Celery/Redis,
        # so generate the file in a threading.Thread worker and return 202
        # immediately with a job id; the admin polls the status endpoint and
        # downloads via a signed, time-limited URL.
        row_count = count_export_rows(slug, days)
        if row_count > _EXPORT_ASYNC_THRESHOLD:
            params = {'slug': slug, 'format': fmt, 'days': days}
            if slug == 'top-sellers':
                params['limit'] = request.query_params.get('limit', 10)
                params['sort'] = request.query_params.get('sort') or 'UNIDADES'
            elif slug == 'customers-rfm':
                params['segment'] = request.query_params.get('segment') or None
            job = ExportJob.objects.create(
                requested_by=request.user, params=params,
            )
            threading.Thread(
                target=_run_export_job, args=(job.pk,), daemon=True,
            ).start()
            return Response(
                {'job_id': job.pk, 'status': job.status},
                status=status.HTTP_202_ACCEPTED,
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
        try:
            response = exporter(payload, fmt)
        except PdfGenerationError as exc:
            # The libharu helper failed/missing (ADR-017 out-of-process render).
            return Response(
                {'codigo_error': 'EXPORT_RENDER_FAILED',
                 'detail': f'PDF rendering failed: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if response is None:
            return Response(
                {'codigo_error': 'FORMAT_NOT_SUPPORTED'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return response


# ─── D-19 async export — job status + signed download ───────────────────


class ExportJobStatusView(_AdminMixin, APIView):
    """GET /reports/export/jobs/<id>/ — status of an async export (D-19).

    Only the admin who requested the job may read it. When the job is DONE,
    the response includes a signed, time-limited (~1h) download URL.
    """

    @extend_schema(
        summary='Async export job status (UC-REP-05, D-19)',
        tags=['reports'],
        responses={200: ExportJobSerializer},
    )
    def get(self, request, job_id):
        try:
            job = ExportJob.objects.get(pk=job_id)
        except ExportJob.DoesNotExist:
            return Response(
                {'codigo_error': 'EXPORT_JOB_NOT_FOUND',
                 'detail': f'Unknown export job: {job_id}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if job.requested_by_id != request.user.id:
            # Do not leak another admin's job existence.
            return Response(
                {'codigo_error': 'EXPORT_JOB_NOT_FOUND',
                 'detail': f'Unknown export job: {job_id}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        download_url = None
        if job.status == ExportJob.STATUS_DONE and job.file_path:
            token = _sign_job_token(job.pk)
            download_url = request.build_absolute_uri(
                f'/api/v2/admin/reports/export/download/{token}/'
            )
        serializer = ExportJobSerializer(
            job, context={'download_url': download_url},
        )
        return Response(serializer.data)


class ExportDownloadView(_AdminMixin, APIView):
    """GET /reports/export/download/<token>/ — stream a generated export.

    The token is a signed TimestampSigner value (max_age 1h). The requesting
    admin must own the job; otherwise the file is not served.
    """

    @extend_schema(
        summary='Download a generated async export (UC-REP-05, D-19)',
        tags=['reports'],
        responses={
            200: OpenApiResponse(description='CSV/XLSX/PDF file.',
                                 response=OpenApiTypes.BINARY),
            400: None,
            403: None,
            404: None,
        },
    )
    def get(self, request, token):
        job_pk = _unsign_job_token(token)
        if job_pk is None:
            return Response(
                {'codigo_error': 'DOWNLOAD_TOKEN_INVALID',
                 'detail': 'The download link is invalid or has expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            job = ExportJob.objects.get(pk=job_pk)
        except ExportJob.DoesNotExist:
            return Response(
                {'codigo_error': 'EXPORT_JOB_NOT_FOUND',
                 'detail': f'Unknown export job: {job_pk}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if job.requested_by_id != request.user.id:
            return Response(
                {'codigo_error': 'EXPORT_DOWNLOAD_FORBIDDEN',
                 'detail': 'You may not download this export.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if job.status != ExportJob.STATUS_DONE or not job.file_path \
                or not os.path.exists(job.file_path):
            return Response(
                {'codigo_error': 'EXPORT_FILE_UNAVAILABLE',
                 'detail': 'The export file is not available.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        fmt = (job.params.get('format') or 'csv').lower()
        content_type = _EXPORT_CONTENT_TYPES.get(fmt, 'application/octet-stream')
        filename = os.path.basename(job.file_path)
        response = FileResponse(
            open(job.file_path, 'rb'), content_type=content_type,
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
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
