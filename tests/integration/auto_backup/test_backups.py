"""Tests — los endpoints de respaldo (UC-ADM-05).

  GET  /api/v2/admin/backups/  ``AdminBackupListView`` — historial
  POST /api/v2/admin/backups/  ``AdminBackupListView`` — disparar ahora

**Un solo mecanismo (DEC-AB-01, :ref:`h-api-768`).** El POST ya no implementa
un respaldo propio: llama a ``DbBackup.action_run_cron()``, que dispara el
mismo ``ir.cron`` que corre el planificador, vía
``IrCron.method_direct_trigger()``. Lo que estos casos verifican es
exactamente eso — que el disparo **entra por el cron** y que la fila que sale
tiene los cuatro campos de la fuente, no una fila huérfana sin archivo.

Los casos que antes probaban ``_run_backup`` —el ``subprocess`` a
``backup_postgres.sh`` en un hilo— desaparecen con él. Su contenido de valor
(la fila de fallo y la alerta por correo) **no** se pierde: se mudó a
``schedule_backup``, donde sirve a los dos caminos, y se prueba en
``test_db_backup.py``.
"""
import os
from unittest import mock

import pytest

from addons.auto_backup.models import DbBackup, DbBackupDetails
from addons.auto_backup.models import db_backup as db_backup_model
from addons.base.models import _PARAM_CACHE, SystemParameter
from addons.base.models.ir_cron import IrCron

pytestmark = pytest.mark.integration

LIST_URL = '/api/v2/admin/backups/'
TRIGGER_URL = '/api/v2/admin/backups/'


@pytest.fixture(autouse=True)
def _clear_param_cache():
    """``backup.alert_email`` vive en SystemParameter (L2, H-API-CFG-01); su
    caché es módulo-nivel (per-proceso), no per-transacción — se limpia entre
    tests para que el rollback de la transacción de pytest-django se refleje
    también en las lecturas cacheadas."""
    _PARAM_CACHE.clear()
    yield
    _PARAM_CACHE.clear()


@pytest.fixture
def config(db, tmp_path):
    """Una configuración de respaldo apuntando a un directorio temporal."""
    return DbBackup.objects.create(name='kaupamex_core_qa', folder=str(tmp_path))


class TestBackupEndpoints:

    # --- permisos ---
    def test_list_anon_401(self, api_client, db):
        assert api_client.get(LIST_URL).status_code == 401

    def test_list_buyer_403(self, auth_client, db):
        assert auth_client.get(LIST_URL).status_code == 403

    def test_trigger_anon_401(self, api_client, db):
        assert api_client.post(TRIGGER_URL).status_code == 401

    def test_trigger_buyer_403(self, auth_client, db):
        assert auth_client.post(TRIGGER_URL).status_code == 403

    # --- listado / estado ---
    def test_admin_lists_the_history(self, admin_client, db):
        DbBackupDetails.objects.create(
            type=DbBackupDetails.TYPE_AUTO, status=DbBackupDetails.STATUS_OK,
        )
        r = admin_client.get(LIST_URL)
        assert r.status_code == 200
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        assert len(rows) == 1
        assert rows[0]['status'] == DbBackupDetails.STATUS_OK


class TestTriggerRunsTheCron:
    """El POST entra por el cron — la propiedad que DEC-AB-01 decide."""

    def test_trigger_produces_a_row_with_the_four_source_fields(
            self, admin_client, config):
        """La fila del disparo a mano ya no es huérfana.

        El camino viejo creaba ``DbBackupDetails(type=MANUAL)`` y nada más:
        sin ``name``, sin ``file_path``, sin ``url`` y sin ``db_backup_id``.
        Esa fila era indescargable por ``BackupDownloadView`` (que exige que
        la ruta caiga bajo una ``DbBackup.folder``) e invisible para
        ``_remove_old_local_backups``. Ahora la produce ``schedule_backup``,
        así que trae los cuatro campos de la fuente.

        ``file_path`` se verifica **en la fila**, no en la respuesta: el
        serializer no lo expone a propósito —es una ruta absoluta del
        servidor y el cliente no la necesita— y esa decisión es anterior a
        DEC-AB-01. Lo que el cliente recibe para descargar es ``url``.
        """
        with mock.patch.object(DbBackup, '_take_dump') as dump:
            dump.side_effect = lambda db_name, stream, model, backup_format='zip': (
                stream.write(b'dump'))
            r = admin_client.post(TRIGGER_URL)

        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        row = rows[0]
        assert row['type'] == DbBackupDetails.TYPE_MANUAL
        assert row['status'] == DbBackupDetails.STATUS_OK
        # Tres de los cuatro campos de la fuente, que el camino viejo dejaba
        # vacíos; el cuarto va abajo, contra la fila.
        assert row['name'].endswith('.zip')
        assert row['url'].startswith('/dbbackup/download/')
        assert row['db_backup_id'] == config.pk

        detail = DbBackupDetails.objects.get()
        assert detail.file_path.startswith(config.folder)
        assert os.path.isfile(detail.file_path)

    def test_the_scheduled_run_stamps_auto(self, config):
        """Sin la clave de contexto, la misma corrida sale ``AUTO``.

        Es la mitad que hace útil el discriminador: ``type`` distingue quién
        disparó, y sólo ``action_run_cron`` pone ``CONTEXT_MANUAL``.
        """
        with mock.patch.object(DbBackup, '_take_dump') as dump:
            dump.side_effect = lambda db_name, stream, model, backup_format='zip': (
                stream.write(b'dump'))
            DbBackup.schedule_backup()

        assert DbBackupDetails.objects.get().type == DbBackupDetails.TYPE_AUTO

    def test_trigger_when_the_job_is_taken_409(self, admin_client, config):
        """Un job ya tomado por otro worker sale 409, no 500.

        ``method_direct_trigger`` levanta ``UserError`` cuando
        ``_acquire_one_job`` devuelve ``None`` — que es lo que el
        ``FOR NO KEY UPDATE SKIP LOCKED`` produce cuando otro proceso tiene
        la fila. Se simula devolviendo ``None``: montar dos conexiones que
        compitan por el lock mediría el motor, no la traducción a 409, que
        es lo que este endpoint decide.
        """
        with mock.patch.object(IrCron, '_acquire_one_job', return_value=None):
            r = admin_client.post(TRIGGER_URL)
        assert r.status_code == 409
        assert r.json()['codigo_error'] == 'BACKUP_IN_PROGRESS'

    def test_trigger_without_a_seeded_cron_503(self, admin_client, config):
        """Sin el cron sembrado no hay nada que disparar, y se dice."""
        IrCron.objects.filter(
            ir_actions_server__model_name='auto_backup.DbBackup',
            ir_actions_server__method_name='schedule_backup',
        ).delete()
        r = admin_client.post(TRIGGER_URL)
        assert r.status_code == 503
        assert r.json()['codigo_error'] == 'BACKUP_CRON_NOT_SEEDED'


class TestBackupFailAlert:
    """La alerta por correo, aislada (``notify_backup_failed``).

    Se mudó de ``controllers/main.py`` al modelo: allá sólo cubría el camino
    bajo demanda, y con un solo mecanismo el aviso tiene que servir a los
    dos. La fuente no alerta en ninguno — su ``except`` sólo escribe dos
    ``_logger.warning`` (``:141-146``).

    ``BACKUP_ALERT_EMAIL`` migró a ``SystemParameter`` L2
    (``backup.alert_email``, H-API-CFG-01): ya no es un setting de Django —
    se sobreescribe con ``set_param``, no con el fixture ``settings``.
    """

    def test_notifies_the_configured_address(self, db, mailoutbox):
        SystemParameter.set_param('backup.alert_email', 'ops@kaupamex.com')
        db_backup_model.notify_backup_failed('kaupamex_core_qa', 'boom')
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ['ops@kaupamex.com']
        assert 'kaupamex_core_qa' in mailoutbox[0].subject

    def test_without_a_recipient_it_neither_sends_nor_breaks(self, db, mailoutbox):
        # 'backup.alert_email' está en _DEFAULT_PARAMETERS -> protegida
        # contra borrado (H-CFG-IMPL-01); no se puede simular "ausente" con
        # delete. Un valor vacío activa el quirk ``or default`` (H-CFG-IMPL-03)
        # y get_param cae al default explícito ('') que pasa el modelo.
        SystemParameter.set_param('backup.alert_email', '')
        db_backup_model.notify_backup_failed('kaupamex_core_qa', 'boom')
        assert len(mailoutbox) == 0

    def test_uses_the_value_seeded_by_the_migration(self, db, mailoutbox):
        # Sin set_param explícito: debe leer el valor sembrado por la
        # migración de datos, no un default local ni el viejo
        # ``settings.BACKUP_ALERT_EMAIL``. Reseed idempotente (== la
        # migración) para no depender de que un test transaction=True previo
        # no haya hecho flush de la fila sembrada.
        SystemParameter.seed()
        db_backup_model.notify_backup_failed('kaupamex_core_qa', 'boom')
        assert len(mailoutbox) == 1
        seeded = SystemParameter.get_param('backup.alert_email')
        assert seeded is not None
        assert 'practicayoruba.com' not in seeded
        assert mailoutbox[0].to == [seeded]
