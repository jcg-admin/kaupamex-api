"""
Views — apps.backups (UC-ADM-05).

GET  /api/v1/admin/backups/          — list backup history
POST /api/v1/admin/backups/trigger/  — trigger an on-demand backup

The actual dump is performed by db/scripts/backup_db.sh (run via
subprocess in a background thread so the HTTP response is immediate).
BackupRecord tracks each execution so the UI can poll/refresh.
"""
import logging
import os
import subprocess
import threading

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BackupRecord
from .serializers import BackupRecordSerializer

logger = logging.getLogger('apps')

# Path to the DB backup script relative to the repo root.
# Adjust if the repos are co-located differently in production.
_BACKUP_SCRIPT = os.path.join(
    os.path.dirname(__file__),          # apps/backups/
    '..', '..', '..', '..',            # up to e-comerce-api/
    '..', 'e-comerce-db',              # sibling repo
    'scripts', 'backup_db.sh',
)
_BACKUP_SCRIPT = os.path.normpath(_BACKUP_SCRIPT)


def _run_backup(record_pk: int) -> None:
    """Execute backup_db.sh and update BackupRecord.status."""
    try:
        result = subprocess.run(
            ['bash', _BACKUP_SCRIPT],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes
        )
        if result.returncode == 0:
            BackupRecord.objects.filter(pk=record_pk).update(
                status=BackupRecord.STATUS_OK,
            )
            logger.info('Backup #%d completado.', record_pk)
        else:
            err = (result.stderr or result.stdout or '')[:1000]
            BackupRecord.objects.filter(pk=record_pk).update(
                status=BackupRecord.STATUS_ERROR,
                error_detail=err,
            )
            logger.error('Backup #%d error: %s', record_pk, err)
    except Exception as exc:
        BackupRecord.objects.filter(pk=record_pk).update(
            status=BackupRecord.STATUS_ERROR,
            error_detail=str(exc)[:1000],
        )
        logger.exception('Backup #%d excepcion inesperada.', record_pk)


class BackupPagination(PageNumberPagination):
    page_size             = 20
    page_size_query_param = 'page_size'
    max_page_size         = 100


class AdminBackupListView(APIView):
    """GET /api/v1/admin/backups/ — UC-ADM-05."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Listar historial de backups (UC-ADM-05)',
        responses={200: BackupRecordSerializer(many=True)},
        tags=['admin-backups'],
    )
    def get(self, request):
        qs = BackupRecord.objects.all()
        paginator = BackupPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                BackupRecordSerializer(page, many=True).data
            )
        return Response(BackupRecordSerializer(qs, many=True).data)


class AdminBackupTriggerView(APIView):
    """POST /api/v1/admin/backups/trigger/ — UC-ADM-05."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Disparar backup manual on-demand (UC-ADM-05)',
        request=None,
        responses={
            202: OpenApiResponse(description='Backup encolado.'),
        },
        tags=['admin-backups'],
    )
    def post(self, request):
        record = BackupRecord.objects.create(type=BackupRecord.TYPE_MANUAL)
        # Run in a background thread — no Celery/Redis per project constraints.
        t = threading.Thread(
            target=_run_backup, args=(record.pk,), daemon=True
        )
        t.start()
        return Response(
            BackupRecordSerializer(record).data,
            status=202,
        )
