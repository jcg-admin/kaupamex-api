"""
Views — addons.auto_backup (UC-ADM-05).

GET  /api/v1/admin/backups/          — list backup history
POST /api/v1/admin/backups/trigger/  — trigger an on-demand backup

The actual dump is performed by db/scripts/backup_db.sh (run via
subprocess in a background thread so the HTTP response is immediate).
DbBackupDetails tracks each execution so the UI can poll/refresh.
"""
import logging
import os
import subprocess
import threading

from django.conf import settings
from django.http import FileResponse
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from addons.authz.permissions import HasCapability
from addons.base.models import SystemParameter
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.mail.models.email_executor import dispatch_email
from addons.auto_backup.models import DbBackup, DbBackupDetails
from addons.auto_backup.controllers.serializers import DbBackupDetailsSerializer

logger = logging.getLogger('apps')


def _notify_backup_failed(record_pk: int, error_detail: str) -> None:
    """
    UC-ADM-05: alerta por email cuando un backup on-demand falla.

    Usa dispatch_email (patrón síncrono del proyecto, sin Celery): si el SMTP
    falla, la alerta se persiste en EmailTask y send_pending_emails la
    reintenta con backoff — los reintentos del propio envío salen gratis.
    No re-lanza: una falla al notificar no debe enmascarar la falla del backup.
    """
    # Migrado desde settings.BACKUP_ALERT_EMAIL (H-API-CFG-01,
    # :ref:`hallazgos-estrategia-configuracion-kaupamex`): tenía default=
    # cableado y stale (practicayoruba.com); ahora vive editable en caliente
    # en SystemParameter (L2, sembrado por addons.base migration 0003).
    recipient = SystemParameter.get_param('backup.alert_email', '')
    if not recipient:
        logger.warning('Backup #%d falló pero BACKUP_ALERT_EMAIL no está '
                       'configurado — no se envió alerta.', record_pk)
        return
    try:
        dispatch_email(
            subject=f'[Kaupamex] Backup #{record_pk} falló',
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
# H-API-765: apuntaba a ``backup_db.sh``, el script de **MariaDB**. El motor
# es PostgreSQL desde ADR-028 y el script vivo es ``backup_postgres.sh``
# (``db/CLAUDE.md``); el viejo sigue en el repo sólo porque hay documentos que
# lo citan, y no sirve a ningún entorno.
_BACKUP_SCRIPT = os.path.join(
    os.path.dirname(__file__),          # addons/auto_backup/controllers/
    '..', '..', '..',                   # up to kaupamex-api/
    '..', 'kaupamex-db',                # sibling repo
    'scripts', 'backup_postgres.sh',
)
_BACKUP_SCRIPT = os.path.normpath(_BACKUP_SCRIPT)


def _run_backup(record_pk: int) -> None:
    """Corre ``backup_postgres.sh`` y sella el estado de la corrida.

    Decía ``backup_db.sh`` y ``BackupRecord.status``: los dos nombres
    murieron —el guion es de MariaDB (:ref:`h-api-765`) y el modelo se
    llama ``DbBackupDetails`` (:ref:`h-api-763`)—.

    Es el camino **bajo demanda**, distinto del programado: aquél lo
    conduce ``DbBackup.schedule_backup`` con la configuración en base. Qué
    frontera queda entre los dos es la decisión pendiente **#610**.
    """
    try:
        result = subprocess.run(
            ['bash', _BACKUP_SCRIPT],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes
        )
        if result.returncode == 0:
            DbBackupDetails.objects.filter(pk=record_pk).update(
                status=DbBackupDetails.STATUS_OK,
            )
            logger.info('Backup #%d completado.', record_pk)
        else:
            err = (result.stderr or result.stdout or '')[:1000]
            DbBackupDetails.objects.filter(pk=record_pk).update(
                status=DbBackupDetails.STATUS_ERROR,
                error_detail=err,
            )
            logger.error('Backup #%d error: %s', record_pk, err)
            _notify_backup_failed(record_pk, err)
    except Exception as exc:
        err = str(exc)[:1000]
        DbBackupDetails.objects.filter(pk=record_pk).update(
            status=DbBackupDetails.STATUS_ERROR,
            error_detail=err,
        )
        logger.exception('Backup #%d excepcion inesperada.', record_pk)
        _notify_backup_failed(record_pk, err)


class BackupPagination(PageNumberPagination):
    page_size             = 20
    page_size_query_param = 'page_size'
    max_page_size         = 100


class AdminBackupListView(APIView):
    """GET|POST /api/v2/admin/backups/ — UC-ADM-05.

    GET  → historial paginado de backups.
    POST → disparar backup manual on-demand (canónico v2; reemplaza trigger/).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'backups.edit'

    @extend_schema(
        summary='Listar historial de backups (UC-ADM-05)',
        responses={200: DbBackupDetailsSerializer(many=True)},
        tags=['admin-backups'],
    )
    def get(self, request):
        qs = DbBackupDetails.objects.all()
        paginator = BackupPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                DbBackupDetailsSerializer(page, many=True).data
            )
        return Response(DbBackupDetailsSerializer(qs, many=True).data)

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
        if not _BACKUP_LOCK.acquire(blocking=False):
            return Response(
                {
                    'detail': 'Ya hay un backup en curso. Intenta de nuevo cuando finalice.',
                    'codigo_error': 'BACKUP_IN_PROGRESS',
                },
                status=409,
            )
        record = DbBackupDetails.objects.create(type=DbBackupDetails.TYPE_MANUAL)

        def _run_and_release(record_pk: int) -> None:
            try:
                _run_backup(record_pk)
            finally:
                _BACKUP_LOCK.release()

        t = threading.Thread(
            target=_run_and_release, args=(record.pk,), daemon=True
        )
        t.start()
        return Response(
            DbBackupDetailsSerializer(record).data,
            status=202,
        )


class BackupDownloadView(APIView):
    """GET /api/v2/admin/backups/download/<path:file_path>/

    Adaptación de ``AppAutoBackup.download_backupfile``
    (``app_auto_backup/controllers/main.py:16``, ruta
    ``/dbbackup/download/<path:file_path>``, LGPL-3).

    Dos divergencias, las dos declaradas:

    1. **La autorización va por capacidad, no por grupo.** La fuente gatea con
       ``has_group('base.group_system')``; aquí el invariante del árbol es
       ``HasCapability`` fail-closed (DEC-11), y la capacidad que dueña este
       dominio ya existe: ``backups``. Usar ``IsAuthenticated`` a secas —o el
       grupo— saltaría el modelo de capacidades.
    2. **La ruta se confina al directorio de respaldos.** La fuente sirve
       *cualquier* archivo del disco cuya ruta el cliente escriba, con un solo
       ``os.path.exists`` de por medio: un usuario del sistema puede leer
       ``/etc/shadow`` por esa ruta. Aquí la ruta resuelta debe caer dentro de
       alguna ``DbBackup.folder`` configurada. Ver :ref:`h-api-766`.
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'backups.edit'

    @extend_schema(
        summary='Descargar un archivo de respaldo (UC-ADM-05)',
        responses={
            200: OpenApiResponse(description='application/octet-stream'),
            404: OpenApiResponse(description='BACKUP_FILE_NOT_FOUND'),
        },
        tags=['admin-backups'],
    )
    def get(self, request, file_path):
        logger.warning('download_backupfile: %s', file_path)
        resolved = os.path.realpath('/' + file_path.lstrip('/'))
        folders = [
            os.path.realpath(folder)
            for folder in DbBackup.objects.values_list('folder', flat=True)
            if folder
        ]
        confined = any(
            resolved == folder or resolved.startswith(folder + os.sep)
            for folder in folders
        )
        if not confined or not os.path.isfile(resolved):
            return Response(
                {
                    'detail': 'File not found',
                    'codigo_error': 'BACKUP_FILE_NOT_FOUND',
                },
                status=404,
            )
        response = FileResponse(
            open(resolved, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = (
            'attachment; filename="%s"' % os.path.basename(resolved))
        return response
