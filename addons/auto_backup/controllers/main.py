"""Endpoints de respaldo — addons.auto_backup (UC-ADM-05).

GET  /api/v2/admin/backups/            — historial paginado
POST /api/v2/admin/backups/            — disparar un respaldo ahora
GET  /api/v2/admin/backups/download/…  — descargar un archivo de respaldo

**Un solo mecanismo (DEC-AB-01, :ref:`h-api-768`).** El POST no implementa un
respaldo propio: dispara el mismo ``ir.cron`` que corre el planificador, vía
``DbBackup.action_run_cron()`` → ``IrCron.method_direct_trigger()``. Es la
forma de la fuente (``app_auto_backup``: su botón *Run Backup* llama
``action_run_cron``, ``views/backup_view.xml:12``), y con ella el disparo a
mano hereda todo lo que el programado ya hacía — el archivo con su nombre, su
ruta bajo ``DbBackup.folder``, su URL de descarga, la FK a la configuración
que lo produjo, la copia a SFTP y la purga de caducados.

Lo que había antes era un **segundo camino**: un ``subprocess`` a
``backup_postgres.sh`` en un hilo, que creaba una fila sin ninguno de esos
cuatro campos — indescargable por ``BackupDownloadView``, invisible para
``_remove_old_local_backups``, y escrita fuera de la carpeta configurada.
"""
import logging
import os

from django.http import FileResponse
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import models
from exceptions import UserError

from addons.authz.permissions import HasCapability
from addons.auto_backup.models import DbBackup, DbBackupDetails
from addons.auto_backup.controllers.serializers import DbBackupDetailsSerializer

logger = logging.getLogger('apps')


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
        summary='Disparar el respaldo ahora (UC-ADM-05)',
        request=None,
        responses={
            200: DbBackupDetailsSerializer(many=True),
            409: OpenApiResponse(description='BACKUP_IN_PROGRESS'),
            503: OpenApiResponse(description='BACKUP_CRON_NOT_SEEDED'),
        },
        tags=['admin-backups'],
    )
    def post(self, request):
        """Corre el cron del respaldo **en el hilo de esta petición**.

        Es lo que la fuente hace y lo dice explícitamente:
        *"Run the CRON job in the current (HTTP) thread"*
        (``odoo19c: odoo/addons/base/models/ir_cron.py:151``). Antes esto
        devolvía 202 y corría en un hilo daemon; el 202 prometía "encolado"
        y el cliente no tenía forma de saber **qué** filas produjo su
        disparo. Ahora la respuesta trae exactamente las corridas de este
        disparo, que es lo que UC-ADM-05 lista.

        DIVERGENCIA declarada, con su costo: la petición **bloquea** lo que
        dure el volcado, y un proxy con timeout corto cerrará la conexión
        antes de la respuesta. El volcado no se pierde por eso —termina en
        disco y su fila queda registrada—, pero el operador no ve el
        resultado. Para bases grandes el camino correcto es el programado,
        que es el mismo mecanismo sin nadie esperando.

        El candado de concurrencia también cambia de naturaleza, y a mejor:
        era un ``threading.Lock`` de proceso cuyo propio comentario alegaba
        *"el proceso Django es un único proceso"* — falso desde ADR-027,
        ``setup/gunicorn.conf.py`` declara ``workers = 4``. Ahora lo hace el
        ``FOR NO KEY UPDATE SKIP LOCKED`` de la fila del cron, que sí cruza
        procesos.
        """
        last_pk_before = DbBackupDetails.objects.aggregate(
            top=models.Max('pk'))['top'] or 0
        try:
            fired = DbBackup.action_run_cron()
        except UserError as exc:
            return Response(
                {
                    'detail': str(exc),
                    'codigo_error': 'BACKUP_IN_PROGRESS',
                },
                status=409,
            )
        if not fired:
            # El cron lo siembra ``migrations/0003_seed_cron_backup``; sin
            # él no hay nada que disparar, y decirlo es más útil que un 200
            # con lista vacía.
            logger.error('El cron del respaldo no está sembrado.')
            return Response(
                {
                    'detail': 'El cron del respaldo no está sembrado.',
                    'codigo_error': 'BACKUP_CRON_NOT_SEEDED',
                },
                status=503,
            )
        runs = DbBackupDetails.objects.filter(pk__gt=last_pk_before)
        return Response(DbBackupDetailsSerializer(runs, many=True).data)


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
