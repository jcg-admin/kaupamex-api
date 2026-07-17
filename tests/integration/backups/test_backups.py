"""
Tests — Backup on-demand admin (UC-ADM-05).

  GET  /api/v2/admin/backups/  AdminBackupListView (historial)
  POST /api/v2/admin/backups/  AdminBackupListView (trigger on-demand)

Cubre: permisos (anon 401, comprador 403), listado/estado, creacion del
BackupRecord (status PENDING), lock de concurrencia (segundo trigger ->
409 BACKUP_IN_PROGRESS), la logica del worker _run_backup (OK / ERROR), y
la notificacion email-on-fail (_notify_backup_failed).

El POST lanza _run_backup en un thread daemon. Para mantener los
tests deterministas, el worker (_run_backup) y la alerta se prueban
directamente; el endpoint se prueba parcheando _run_backup para no tocar
el script real ni la BD desde el thread.
"""
import pytest
from unittest import mock

from django.core import mail

from addons.backups import views as backups_views
from addons.backups.models import BackupRecord

pytestmark = pytest.mark.integration

LIST_URL    = '/api/v2/admin/backups/'
TRIGGER_URL = '/api/v2/admin/backups/'


@pytest.fixture(autouse=True)
def _free_backup_lock():
    """Garantiza que el lock global de proceso esté libre antes/después."""
    if backups_views._BACKUP_LOCK.locked():
        backups_views._BACKUP_LOCK.release()
    yield
    if backups_views._BACKUP_LOCK.locked():
        backups_views._BACKUP_LOCK.release()


class TestBackupEndpoints:

    # --- permisos ---
    def test_list_anon_401(self, api_client, db):
        assert api_client.get(LIST_URL).status_code == 401

    def test_list_comprador_403(self, auth_client, db):
        assert auth_client.get(LIST_URL).status_code == 403

    def test_trigger_anon_401(self, api_client, db):
        assert api_client.post(TRIGGER_URL).status_code == 401

    def test_trigger_comprador_403(self, auth_client, db):
        assert auth_client.post(TRIGGER_URL).status_code == 403

    # --- listado / estado ---
    def test_admin_lista_historial(self, admin_client, db):
        BackupRecord.objects.create(
            type=BackupRecord.TYPE_AUTO, status=BackupRecord.STATUS_OK,
        )
        r = admin_client.get(LIST_URL)
        assert r.status_code == 200
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        assert len(rows) == 1
        assert rows[0]['status'] == BackupRecord.STATUS_OK

    # --- trigger crea record PENDING ---
    def test_trigger_crea_record_pending(self, admin_client, db):
        # Parchear el worker para que el thread no ejecute el script real.
        with mock.patch.object(backups_views, '_run_backup'):
            r = admin_client.post(TRIGGER_URL)
        assert r.status_code == 202
        body = r.json()
        assert body['type'] == BackupRecord.TYPE_MANUAL
        assert body['status'] == BackupRecord.STATUS_PENDING
        assert BackupRecord.objects.filter(pk=body['id']).exists()

    # --- lock de concurrencia ---
    def test_segundo_trigger_concurrente_409(self, admin_client, db):
        """Si el lock ya está tomado, el segundo trigger devuelve 409."""
        # Simular backup en curso tomando el lock manualmente.
        acquired = backups_views._BACKUP_LOCK.acquire(blocking=False)
        assert acquired
        try:
            r = admin_client.post(TRIGGER_URL)
        finally:
            backups_views._BACKUP_LOCK.release()
        assert r.status_code == 409
        assert r.json()['codigo_error'] == 'BACKUP_IN_PROGRESS'


class TestBackupWorker:
    """Logica del worker _run_backup ejecutada sincronamente."""

    def test_run_backup_ok_marca_status_ok(self, db):
        record = BackupRecord.objects.create(type=BackupRecord.TYPE_MANUAL)
        fake = mock.Mock(returncode=0, stdout='ok', stderr='')
        with mock.patch.object(backups_views.subprocess, 'run', return_value=fake):
            backups_views._run_backup(record.pk)
        record.refresh_from_db()
        assert record.status == BackupRecord.STATUS_OK

    def test_run_backup_error_marca_status_error_y_notifica(self, db):
        mail.outbox = []
        record = BackupRecord.objects.create(type=BackupRecord.TYPE_MANUAL)
        fake = mock.Mock(returncode=1, stdout='', stderr='dump failed: disk full')
        with mock.patch.object(backups_views.subprocess, 'run', return_value=fake):
            backups_views._run_backup(record.pk)
        record.refresh_from_db()
        assert record.status == BackupRecord.STATUS_ERROR
        assert 'disk full' in record.error_detail
        # email-on-fail: dispatch_email es síncrono en testing (DISPATCH_EMAIL_SYNC).
        assert len(mail.outbox) == 1
        assert 'falló' in mail.outbox[0].subject

    def test_run_backup_excepcion_marca_error_y_notifica(self, db):
        mail.outbox = []
        record = BackupRecord.objects.create(type=BackupRecord.TYPE_MANUAL)
        with mock.patch.object(backups_views.subprocess, 'run',
                               side_effect=OSError('bash not found')):
            backups_views._run_backup(record.pk)
        record.refresh_from_db()
        assert record.status == BackupRecord.STATUS_ERROR
        assert 'bash not found' in record.error_detail
        assert len(mail.outbox) == 1


class TestBackupFailAlert:
    """Notificacion email-on-fail aislada (_notify_backup_failed)."""

    def test_notifica_a_backup_alert_email(self, db, settings):
        settings.BACKUP_ALERT_EMAIL = 'ops@practicayoruba.mx'
        mail.outbox = []
        backups_views._notify_backup_failed(42, 'boom')
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ['ops@practicayoruba.mx']
        assert '42' in mail.outbox[0].subject

    def test_sin_destinatario_no_envia_ni_rompe(self, db, settings):
        settings.BACKUP_ALERT_EMAIL = ''
        mail.outbox = []
        # No debe lanzar ni enviar cuando no hay destinatario configurado.
        backups_views._notify_backup_failed(7, 'boom')
        assert len(mail.outbox) == 0
