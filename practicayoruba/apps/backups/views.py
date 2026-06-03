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

from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.email_executor import dispatch_email
from .models import BackupRecord
from .serializers import BackupRecordSerializer

logger = logging.getLogger('apps')


def _notify_backup_failed(record_pk: int, error_detail: str) -> None:
    """
    UC-ADM-05: alerta por email cuando un backup on-demand falla.

    Usa dispatch_email (patrón síncrono del proyecto, sin Celery): si el SMTP
    falla, la alerta se persiste en EmailTask y send_pending_emails la
    reintenta con backoff — los reintentos del propio envío salen gratis.
    No re-lanza: una falla al notificar no debe enmascarar la falla del backup.
    """
    recipient = getattr(settings, 'BACKUP_ALERT_EMAIL', '')
    if not recipient:
        logger.warning('Backup #%d falló pero BACKUP_ALERT_EMAIL no está '
                       'configurado — no se envió alerta.', record_pk)
        return
    try:
        dispatch_email(
            subject=f'[PracticaYoruba] Backup #{record_pk} falló',
            message=(
                f'El backup on-demand #{record_pk} terminó en error.\n\n'
                f'Detalle:\n{error_detail}'
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[recipient],
        )
    except Exception:
        logger.exception('No se pudo despachar la alerta de backup fallido #%d.',
                         record_pk)

# H-CICLO82-03: lock en proceso para serializar peticiones concurrentes de
# backup. Sin este lock, N POST simultaneos a /backups/trigger/ lanzan N
# threads de backup_db.sh al mismo tiempo, corrompiendo el dump (escrituras
# concurrentes sobre el mismo archivo de destino) y saturando I/O del VPS.
# Un threading.Lock es suficiente porque el proceso Django es un unico proceso
# (mod_wsgi/WSGI — no Celery, no workers separados).
_BACKUP_LOCK = threading.Lock()

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
            _notify_backup_failed(record_pk, err)
    except Exception as exc:
        err = str(exc)[:1000]
        BackupRecord.objects.filter(pk=record_pk).update(
            status=BackupRecord.STATUS_ERROR,
            error_detail=err,
        )
        logger.exception('Backup #%d excepcion inesperada.', record_pk)
        _notify_backup_failed(record_pk, err)


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
        # H-CICLO82-03: rechazar si ya hay un backup en curso.
        # _BACKUP_LOCK.acquire(blocking=False) devuelve False inmediatamente
        # si el lock ya esta tomado (backup activo), evitando N threads
        # simultaneos de backup_db.sh.
        if not _BACKUP_LOCK.acquire(blocking=False):
            return Response(
                {
                    'detail': 'Ya hay un backup en curso. Intenta de nuevo cuando finalice.',
                    'codigo_error': 'BACKUP_IN_PROGRESS',
                },
                status=409,
            )
        record = BackupRecord.objects.create(type=BackupRecord.TYPE_MANUAL)

        def _run_and_release(record_pk: int) -> None:
            try:
                _run_backup(record_pk)
            finally:
                _BACKUP_LOCK.release()

        # Run in a background thread — no Celery/Redis per project constraints.
        t = threading.Thread(
            target=_run_and_release, args=(record.pk,), daemon=True
        )
        t.start()
        return Response(
            BackupRecordSerializer(record).data,
            status=202,
        )
