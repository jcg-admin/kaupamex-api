"""Tests — ``db.backup`` y ``db.backup.details``, la forma de ``app_auto_backup``.

Adaptación de ``app_auto_backup`` (``odoo-tools@622ddc2a``,
``18.x/app-odoo-18.0``, **LGPL-3**). La fuente **no trae suite**: medido,
``18.x/app-odoo-18.0/app_auto_backup/`` no tiene directorio ``tests/``, así
que aquí no hay caso que adaptar verbatim — cada uno se escribe contra el
contrato que el archivo de la referencia declara, citando su línea.

Cubre lo que el porte añadió y lo que corrigió:

- la **cabecera** de los dos modelos (``atributos-de-clase-de-modelo.md``);
- el **planificador** — ``schedule_backup`` y su ``ir.cron`` de 12 h, que
  antes no existía (:ref:`h-api-763`);
- la **guarda de autorización** de ``_take_dump``, que la fuente porta
  entera: sólo el usuario del cron vuelca;
- la corrección del ``finally`` de ``test_sftp_connection``, que en la
  fuente enmascara el error real con un ``NameError`` (:ref:`h-api-764`);
- el ciclo de vida del archivo en ``DbBackupDetails.delete()``.
"""
import os
from unittest import mock

import pytest
from django.db import DEFAULT_DB_ALIAS, connections

from addons.auto_backup.data import CRON_BACKUP
from addons.auto_backup.models import DbBackup, DbBackupDetails
from addons.auto_backup.models.db_backup import _get_db_name
from addons.base.models.ir_cron import IrCron
from exceptions import AccessDenied, UserError, ValidationError

pytestmark = pytest.mark.integration


@pytest.fixture
def config(db, tmp_path):
    """Una configuración de respaldo apuntando a un directorio temporal."""
    return DbBackup.objects.create(name='kaupamex_core_qa', folder=str(tmp_path))


class TestHeader:
    """Los atributos de clase que la fuente declara — ``:28-29``, ``:10-12``."""

    def test_db_backup_declares_name_and_description(self):
        assert DbBackup._name == 'db.backup'
        assert DbBackup._description == 'Backup configuration record'

    def test_db_backup_details_declares_the_three(self):
        assert DbBackupDetails._name == 'db.backup.details'
        assert DbBackupDetails._description == 'Database Backup Details'
        assert DbBackupDetails._order == 'id desc'

    def test_the_table_derives_from_name(self):
        """``_table = _name.replace('.', '_')`` — ``model_classes.py:266``."""
        assert DbBackup._meta.db_table == DbBackup._name.replace('.', '_')
        assert (DbBackupDetails._meta.db_table
                == DbBackupDetails._name.replace('.', '_'))

    def test_meta_ordering_derives_from_order(self):
        assert DbBackupDetails._meta.ordering == ['-id']


class TestDefaults:
    """Los ``default=`` de la fuente — ``:31-47``."""

    def test_name_default_is_the_current_database(self, db):
        assert _get_db_name() == connections[DEFAULT_DB_ALIAS].settings_dict['NAME']

    def test_the_defaults_of_the_source(self, db):
        rec = DbBackup.objects.create(folder='/tmp/kaupamex-test')
        assert rec.host == 'localhost'
        assert rec.port == '8069'
        assert rec.backup_type == 'zip'
        assert rec.autoremove is False
        assert rec.days_to_keep == 30
        assert rec.sftp_write is False
        assert rec.sftp_port == 22
        assert rec.name == _get_db_name()


class TestSeededCron:
    """El ``ir.cron`` de 12 h — ``data/backup_data.xml:4-13``.

    Antes del porte el método existía y **nadie lo llamaba**: la misma forma
    que :ref:`h-api-747` registró para el barrido de ``@api.autovacuum``.
    """

    def _cron(self):
        return IrCron.objects.filter(
            ir_actions_server__model_name=CRON_BACKUP['model_name'],
            ir_actions_server__method_name=CRON_BACKUP['method_name'],
        ).first()

    def test_cron_exists_with_the_source_interval(self, db):
        cron = self._cron()
        assert cron is not None
        assert cron.interval_number == 12
        assert cron.interval_type == 'hours'
        assert cron.priority == 5
        assert cron.active is True

    def test_the_action_points_to_the_class_method(self, db):
        cron = self._cron()
        assert cron.ir_actions_server.model_name == 'auto_backup.DbBackup'
        assert cron.ir_actions_server.method_name == 'schedule_backup'
        # El método al que apunta tiene que existir y ser invocable.
        assert callable(getattr(DbBackup, 'schedule_backup'))


class TestScheduleBackup:
    """``schedule_backup`` — ``:118``.

    ``_take_dump`` se parchea: su guarda de autorización exige ser el usuario
    del cron, y volcar la base de pruebas de verdad no es lo que este caso
    mide. Lo que se mide es el recorrido: nombre del archivo, fila de
    detalle, y el enlace a la configuración que la produjo.
    """

    def _fake_dump(self, content=b'DUMP'):
        def _write(self_, db_name, stream, model, backup_format='zip'):
            stream.write(content)
        return _write

    def test_creates_the_detail_row_linked_to_its_config(self, config):
        with mock.patch.object(DbBackup, '_take_dump', self._fake_dump()):
            DbBackup.schedule_backup()

        detail = DbBackupDetails.objects.get()
        assert detail.db_backup_id_id == config.pk
        assert detail.type == DbBackupDetails.TYPE_AUTO
        assert detail.status == DbBackupDetails.STATUS_OK
        assert detail.size_bytes == 4
        assert os.path.isfile(detail.file_path)

    def test_the_file_name_follows_the_source_form(self, config):
        """``'%s_%s.%s' % (strftime, name, backup_type)`` — ``:126``."""
        with mock.patch.object(DbBackup, '_take_dump', self._fake_dump()):
            DbBackup.schedule_backup()

        detail = DbBackupDetails.objects.get()
        assert detail.name.endswith('_%s.zip' % config.name)
        assert detail.url == '/dbbackup/download/%s' % detail.file_path

    def test_creates_the_folder_if_missing(self, db, tmp_path):
        destination = tmp_path / 'no' / 'existe'
        DbBackup.objects.create(name='kaupamex_core_qa', folder=str(destination))
        with mock.patch.object(DbBackup, '_take_dump', self._fake_dump()):
            DbBackup.schedule_backup()
        assert destination.is_dir()

    def test_one_failure_does_not_stop_the_run(self, db, tmp_path):
        """``except … continue`` — ``:139``: la segunda configuración corre.

        DIVERGENCIA declarada (DEC-AB-01, :ref:`h-api-768`): la fuente hace
        ``continue`` y no deja rastro del fallo fuera del log, así que su
        historial sólo contiene éxitos. Aquí el fallo **también** produce
        fila, con ``status=ERROR`` y su ``error_detail`` — es la capacidad
        que el camino bajo demanda tenía y que al unificar los mecanismos
        pasa a servir a los dos.
        """
        DbBackup.objects.create(name='rota', folder=str(tmp_path / 'a'))
        DbBackup.objects.create(name='sana', folder=str(tmp_path / 'b'))

        def _sometimes(self_, db_name, stream, model, backup_format='zip'):
            if db_name == 'rota':
                raise RuntimeError('bad database administrator password')
            stream.write(b'DUMP')

        with mock.patch.object(DbBackup, '_take_dump', _sometimes, create=False):
            DbBackup.schedule_backup()

        ok = DbBackupDetails.objects.get(status=DbBackupDetails.STATUS_OK)
        assert ok.name.endswith('_sana.zip')

        failed = DbBackupDetails.objects.get(status=DbBackupDetails.STATUS_ERROR)
        assert failed.name.endswith('_rota.zip')
        assert 'bad database administrator password' in failed.error_detail
        assert DbBackupDetails.objects.count() == 2

    def test_without_configs_it_does_nothing(self, db):
        DbBackup.objects.all().delete()
        DbBackup.schedule_backup()
        assert DbBackupDetails.objects.count() == 0

    def test_does_not_touch_the_remote_when_sftp_write_is_off(self, config):
        with mock.patch.object(DbBackup, '_take_dump', self._fake_dump()), \
             mock.patch.object(DbBackup, '_copy_to_sftp') as copy_mock:
            DbBackup.schedule_backup()
        copy_mock.assert_not_called()

    def test_copies_to_the_remote_when_sftp_write_is_on(self, config):
        config.sftp_write = True
        config.save(update_fields=['sftp_write'])
        with mock.patch.object(DbBackup, '_take_dump', self._fake_dump()), \
             mock.patch.object(DbBackup, '_copy_to_sftp') as copy_mock:
            DbBackup.schedule_backup()
        copy_mock.assert_called_once()


class TestAuthorizationGuard:
    """``_take_dump`` sólo vuelca para el usuario del cron — ``:283-291``.

    La fuente porta esta guarda entera y su razón sigue vigente: el volcado
    esquiva ``check_db_management_enabled``, así que la única llave es que
    quien lo pida sea el job.
    """

    def test_a_user_other_than_the_cron_one_cannot_dump(self, config):
        with pytest.raises(AccessDenied):
            config._take_dump(config.name, None, 'db.backup')

    def test_no_authenticated_user_either(self, config):
        """El hueco que la transliteración abría — :ref:`h-api-766`.

        Con ``get_current_uid()`` en ``None`` y el cron sin usuario, la
        comparación de la fuente (``cron_user_id != current_uid``) es
        ``None != None`` → falsa, y la guarda deja pasar. Fail-closed.
        """
        IrCron.objects.filter(
            ir_actions_server__model_name=CRON_BACKUP['model_name'],
        ).update(user=None)
        with mock.patch('addons.auto_backup.models.db_backup.get_current_uid',
                        return_value=None):
            with pytest.raises(AccessDenied):
                config._take_dump(config.name, None, 'db.backup')


class TestManifest:
    """``_dump_db_manifest`` — ``:328``, sobre psycopg 3."""

    def test_the_manifest_reads_the_server_version(self, config):
        """La fuente usa ``cr._obj.connection.server_version`` (psycopg2).

        Ese atributo **no existe** en psycopg 3; transliterado revienta con
        ``AttributeError`` en cada volcado ``zip`` (:ref:`h-api-766`).
        """
        with connections[DEFAULT_DB_ALIAS].cursor() as cursor:
            manifest = config._dump_db_manifest(cursor)

        assert manifest['odoo_dump'] == '1'
        assert manifest['db_name'] == _get_db_name()
        # '16.13' → '160.13' sería el síntoma de una división mal portada.
        major, _dot, _minor = manifest['pg_version'].partition('.')
        assert major.isdigit() and 9 <= int(major) <= 99
        assert isinstance(manifest['modules'], dict)


class TestSftpConnection:
    """``test_sftp_connection`` — ``:82``, con el ``finally`` corregido."""

    def test_the_ssh_client_failure_is_not_masked(self, config):
        """El defecto de la fuente: su ``finally`` lee ``s`` sin asignar.

        Con ``SSHClient()`` reventando, allá el ``NameError`` sustituye al
        error real. Aquí sale el mensaje verdadero. Ver :ref:`h-api-764`.
        """
        with mock.patch('addons.auto_backup.models.db_backup.paramiko.SSHClient',
                        side_effect=OSError('no hay transporte')):
            with pytest.raises(ValidationError) as exc:
                config.test_sftp_connection()
        assert 'no hay transporte' in str(exc.value)
        assert 'NameError' not in str(exc.value)

    def test_success_also_raises(self, config):
        """El idioma de la fuente: las dos ramas levantan ``ValidationError``."""
        client = mock.MagicMock()
        with mock.patch('addons.auto_backup.models.db_backup.paramiko.SSHClient',
                        return_value=client):
            with pytest.raises(ValidationError) as exc:
                config.test_sftp_connection()
        assert 'Succeeded' in str(exc.value)
        client.close.assert_called_once()


class TestDetailLifecycle:
    """``action_download_file`` / ``unlink`` / ``action_remove_file``."""

    def test_the_download_descriptor_matches_the_source(self, db):
        detail = DbBackupDetails.objects.create(
            name='x.zip', file_path='/tmp/x.zip', url='/dbbackup/download//tmp/x.zip')
        assert detail.action_download_file() == {
            'type': 'ir.actions.act_url',
            'url': '/dbbackup/download//tmp/x.zip',
            'target': 'new',
        }

    def test_without_path_or_url_it_raises(self, db):
        detail = DbBackupDetails.objects.create(name='x.zip')
        with pytest.raises(UserError):
            detail.action_download_file()

    def test_delete_removes_the_file_from_disk(self, db, tmp_path):
        backup_file = tmp_path / 'x.zip'
        backup_file.write_bytes(b'DUMP')
        detail = DbBackupDetails.objects.create(
            name='x.zip', file_path=str(backup_file))
        detail.action_remove_file()
        assert not backup_file.exists()
        assert DbBackupDetails.objects.count() == 0

    def test_an_already_deleted_file_does_not_block_row_removal(self, db, tmp_path):
        """El ``except`` ancho de la fuente — un borrado a mano no bloquea."""
        detail = DbBackupDetails.objects.create(
            name='x.zip', file_path=str(tmp_path / 'no-existe.zip'))
        detail.action_remove_file()
        assert DbBackupDetails.objects.count() == 0


class TestLocalPurge:
    """``_remove_old_local_backups`` — ``:249-275``."""

    def _age_file(self, path, days):
        older = os.stat(path).st_mtime - days * 86400
        os.utime(path, (older, older))

    def test_keeps_the_recent_ones(self, config, tmp_path):
        backup_file = tmp_path / ('%s_reciente.zip' % config.name)
        backup_file.write_bytes(b'DUMP')
        config._remove_old_local_backups()
        assert backup_file.exists()

    def test_ignores_files_without_the_database_name(self, config, tmp_path):
        """``if self.name not in fullpath: continue`` — ``:255``."""
        foreign_file = tmp_path / 'otra_base.zip'
        foreign_file.write_bytes(b'DUMP')
        config._remove_old_local_backups()
        assert foreign_file.exists()
