"""``db.backup`` — la configuración del respaldo programado.

Adaptación de ``app_auto_backup/models/db_backup.py``
(``odoo-tools@622ddc2a``, ``18.x/app-odoo-18.0``, **LGPL-3** derivado de su
``__manifest__.py`` — copia + adaptación con atribución, DEC-KX-03).

**Por qué este archivo no existía.** El manifest de este addon declaraba
*"la referencia Community no tiene addon de respaldo"*, y sobre esa premisa
el addon se quedó con un solo modelo —la **ejecución**— y ninguna
**configuración**. La premisa era falsa: ``app_auto_backup`` existe, y es la
contraparte real (:ref:`h-api-763`). El par de modelos de la fuente es
``db.backup`` (dónde, cómo, cuánto se conserva) y ``db.backup.details`` (qué
pasó en cada corrida); aquí sólo estaba el segundo, con otro nombre.

Cobertura contra la fuente — 17 campos, 7 métodos
==================================================

.. list-table::
   :header-rows: 1
   :widths: 26 16 58

   * - Símbolo
     - Desenlace
     - Detalle
   * - los 17 campos
     - PORTADOS
     - verbatim, con dos defaults readaptados (ver abajo)
   * - ``_get_db_name``
     - PORTADO, otro ámbito
     - ``default=`` de Django exige un invocable **sin argumentos**; un
       método no lo es. Se porta como función de módulo — mismo nombre y
       misma visibilidad, distinto ámbito. Precedente en el árbol:
       ``_default_country`` de ``hr_departure_reason.py``.
   * - ``test_sftp_connection``
     - PORTADO
     - con ``paramiko``, declarado en ``pyproject.toml``. Corrige un defecto
       de la fuente: su ``finally`` lee ``s`` sin inicializar
       (:ref:`h-api-764`).
   * - ``schedule_backup``
     - PORTADO
     - ``@api.model`` → ``classmethod``, el idioma declarado de este árbol.
   * - ``_take_dump``
     - PORTADO
     - reusa ``service.db._pg_env``/``database_exists`` y **no** pasa por
       ``ensure_management_enabled()``, que es exactamente lo que la fuente
       persigue al duplicar ``service/db.py``: *"This allows us to disable
       the Odoo database manager which is a MUCH safer way"*. Su guarda de
       autorización se porta entera.
   * - ``_dump_db_manifest``
     - PORTADO
     - ``latest_version`` → ``version``: ``ir.module.module`` aquí no declara
       la primera (``src/addons/base/models/ir_module.py:184``). El
       ``odoo_dump``/``version``/``version_info``/``major_version`` salen de
       ``src/release.py``, el espejo de ``odoo/release.py``.
   * - ``action_view_cron``
     - NO PORTADO
     - navegación pura: devuelve la acción de ventana que
       ``ir.actions.actions._for_xml_id`` resuelve, y ese método **no existe
       en el árbol** (0 definiciones). Es la *Causa C* que ya declaran
       ``purchase_stock/models/purchase_order.py:118`` y otros cinco
       archivos; el desenlace es el mismo aquí. Sucesor: tarea **#273**,
       que siembra las acciones de ventana y el renderizador que ``_for_xml_id``
       exige.
   * - ``action_run_cron``
     - PORTADO
     - ``cron.method_direct_trigger()`` → ``IrCron._acquire_one_job(...,
       include_not_ready=True)`` + ``_run_job()``, que es el equivalente que
       ``ir_cron.py:384`` ya declara ("== Odoo ``method_direct_trigger``").

Dos defaults readaptados, y por qué
------------------------------------

- ``folder`` — la fuente declara ``/usr/lib/python3/dist-packages/odoo/
  backups``, la ruta de instalación de **su** producto. Aquí es
  ``/var/backups/kaupamex``, que es donde el sistema operativo pone los
  respaldos y donde ``db: scripts/backup_postgres.sh`` ya escribe.
- ``name`` — su default es el nombre de la base viva; se conserva la forma
  (invocable), leyendo el alias por defecto de Django.

``host``/``port`` se portan **verbatim con su default**: en la fuente sólo
alimentan la línea de log del fallo — la variable ``uri`` que construyen no
la lee nadie (:ref:`h-api-764`). Inventarles un valor sería suponer un
consumidor que no existe.
"""
import datetime
import json
import logging
import os
import subprocess
import tempfile
import time
import zipfile

import paramiko
from django.db import DEFAULT_DB_ALIAS, connections, transaction

import fields
import release
from exceptions import AccessDenied, ValidationError
from tools.translate import _

from addons.auto_backup.models.db_backup_details import DbBackupDetails
from addons.base.models import SystemParameter, TimeStampedModel
from addons.base.models.ir_cron import IrCron
from addons.base.models.ir_module import IrModule
from addons.mail.models.email_executor import dispatch_email
from orm.environments import get_current_uid
from service.db import _pg_env, database_exists

_logger = logging.getLogger(__name__)

#: Los dos formatos que la fuente declara en ``backup_type``.
BACKUP_TYPES = [('zip', 'Zip'), ('dump', 'Dump')]


def _get_db_name():
    """El nombre de la base viva — ≙ ``self._cr.dbname`` de la fuente.

    Función de módulo y no método por el contrato de ``default=`` de Django
    (invocable sin argumentos); ver la tabla de cobertura del módulo.
    """
    return connections[DEFAULT_DB_ALIAS].settings_dict['NAME']


class DbBackup(TimeStampedModel):
    """``db.backup`` — una configuración de respaldo programado."""

    # Atributos de clase de modelo — los dos que la fuente declara
    # (``app_auto_backup/models/db_backup.py:28-29``), verbatim.
    _name = 'db.backup'
    _description = 'Backup configuration record'

    # --- Configuración del servidor local ---
    host = fields.Char(
        'Host', default='localhost',
        help_text='Odoo host. Sólo alimenta la línea de log del fallo.',
    )
    port = fields.Char(
        'Port', default='8069',
        help_text='Odoo port. Sólo alimenta la línea de log del fallo.',
    )
    name = fields.Char(
        'Database', default=_get_db_name,
        help_text='Base que se quiere respaldar (Odoo name).',
    )
    folder = fields.Char(
        'Backup Directory', default='/var/backups/kaupamex',
        help_text='Ruta absoluta donde se escriben los respaldos (Odoo folder).',
    )
    backup_type = fields.Selection(
        'Backup Type', max_length=8, choices=BACKUP_TYPES, default='zip',
        help_text='Formato del volcado (Odoo backup_type).',
    )
    autoremove = fields.Boolean(
        'Auto. Remove Backups', default=False,
        help_text=(
            'Si se marca, los respaldos locales se borran pasados '
            'days_to_keep días (Odoo autoremove).'
        ),
    )
    days_to_keep = fields.Integer(
        'Remove after x days', default=30,
        help_text=(
            'Tras cuántos días se borra el respaldo local. Con 5, los '
            'respaldos se retiran a los 5 días (Odoo days_to_keep).'
        ),
    )

    # --- Configuración del servidor externo (SFTP) ---
    sftp_write = fields.Boolean(
        'Write to external server with sftp', default=False,
        help_text='Copiar además el respaldo a un servidor remoto por SFTP.',
    )
    sftp_path = fields.Char(
        'Path external server', blank=True, default='',
        help_text=(
            'Carpeta del servidor remoto donde se escriben los volcados, '
            'p. ej. /odoo/backups/ (Odoo sftp_path).'
        ),
    )
    sftp_host = fields.Char(
        'IP Address SFTP Server', blank=True, default='',
        help_text='Dirección del servidor remoto (Odoo sftp_host).',
    )
    sftp_port = fields.Integer(
        'SFTP Port', default=22,
        help_text='Puerto SSH/SFTP del servidor remoto (Odoo sftp_port).',
    )
    sftp_user = fields.Char(
        'Username SFTP Server', blank=True, default='',
        help_text='Usuario del servidor remoto (Odoo sftp_user).',
    )
    sftp_password = fields.Char(
        'Password User SFTP Server', blank=True, default='',
        help_text=(
            'SECRETO — contraseña del usuario remoto (Odoo sftp_password). '
            'La superficie que lo exponga debe ir gateada por capacidad.'
        ),
    )
    days_to_keep_sftp = fields.Integer(
        'Remove SFTP after x days', default=30,
        help_text='Tras cuántos días se borra el respaldo del remoto.',
    )
    send_mail_sftp_fail = fields.Boolean(
        'Auto. E-mail on backup fail', default=False,
        help_text='Avisar por correo cuando la copia al remoto falle.',
    )
    email_to_notify = fields.Char(
        'E-mail to notify', blank=True, default='',
        help_text='Destinatario del aviso de fallo (Odoo email_to_notify).',
    )

    class Meta:
        # Derivado de ``_name`` — ``check_table_matches_name()`` lo verifica.
        db_table = 'db_backup'
        ordering = ['id']
        verbose_name = 'Configuración de respaldo'
        verbose_name_plural = 'Configuraciones de respaldo'

    def __str__(self):
        return f'{self.name} → {self.folder}'

    # ``backup_details_ids`` es el One2many de la fuente; su contraparte aquí
    # es el ``related_name='backup_details_ids'`` de la FK que declara
    # ``DbBackupDetails.db_backup_id`` — el lado que Django persiste.

    def test_sftp_connection(self, context=None):
        """Prueba la conexión SFTP y **siempre** levanta — ≙ ``:82``.

        El idioma de la fuente es levantar ``ValidationError`` también en el
        caso de éxito: allá es cómo un botón de formulario muestra un diálogo.
        Se conserva porque es el contrato del método, no un accidente; quien
        lo exponga por HTTP decide cómo traduce las dos ramas.

        **Corrige un defecto de la fuente:** su ``finally`` hace ``if s:``
        cuando ``paramiko.SSHClient()`` pudo no llegar a asignarse, lo que
        cambia el error real por un ``NameError``. Ver :ref:`h-api-764`.
        """
        message_title = ''
        message_content = ''
        error = ''
        has_failed = False
        client = None

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(self.sftp_host, self.sftp_port, self.sftp_user,
                           self.sftp_password, timeout=10)
            sftp = client.open_sftp()
            sftp.close()
            message_title = _('Connection Test Succeeded!\n'
                              'Everything seems properly set up for FTP back-ups!')
        except Exception as exc:  # noqa: BLE001 — la fuente reporta cualquier fallo
            _logger.critical('There was a problem connecting to the remote ftp: %s',
                             str(exc))
            error += str(exc)
            has_failed = True
            message_title = _('Connection Test Failed!')
            if len(self.sftp_host or '') < 8:
                message_content += '\nYour IP address seems to be too short.\n'
            message_content += _('Here is what we got instead:\n')
        finally:
            if client is not None:
                client.close()

        if has_failed:
            raise ValidationError(message_title + '\n\n' + message_content + str(error))
        raise ValidationError(message_title + '\n\n' + message_content)

    @classmethod
    def schedule_backup(cls):
        """Recorre todas las configuraciones y respalda cada una — ≙ ``:118``.

        Es el método que el ``ir.cron`` de 12 h invoca (``data/backup.py``).
        ``@api.model`` → ``classmethod``, el idioma declarado de este árbol.
        """
        for rec in cls.objects.all():
            if not os.path.isdir(rec.folder):
                os.makedirs(rec.folder, exist_ok=True)
            # Nombre del volcado — ≙ ``:126``.
            bkp_file = '%s_%s.%s' % (
                time.strftime('%Y_%m_%d_%H_%M_%S'), rec.name, rec.backup_type)
            file_path = os.path.join(rec.folder, bkp_file)
            try:
                with open(file_path, 'wb') as stream:
                    rec._take_dump(rec.name, stream, 'db.backup', rec.backup_type)
                rec.backup_details_ids.create(
                    name=bkp_file,
                    file_path=file_path,
                    url='/dbbackup/download/%s' % file_path,
                    # Los dos campos propios que la fuente no tiene: esta
                    # corrida es programada y terminó bien.
                    type=DbBackupDetails.TYPE_AUTO,
                    status=DbBackupDetails.STATUS_OK,
                    size_bytes=os.path.getsize(file_path),
                )
            except Exception as error:  # noqa: BLE001 — un fallo no corta el recorrido
                _logger.warning(
                    "Couldn't backup database %s. Bad database administrator "
                    'password for server running at http://%s:%s',
                    rec.name, rec.host, rec.port)
                _logger.warning('Exact error from the exception: %s', str(error))
                continue

            if rec.sftp_write:
                rec._copy_to_sftp()

            if rec.autoremove:
                rec._remove_old_local_backups()

    def _copy_to_sftp(self):
        """Sube los volcados al remoto y purga los caducados — ≙ ``:148-247``.

        Se extrae a método propio: en la fuente es un bloque de cien líneas
        dentro de ``schedule_backup``. La extracción **no** cambia qué hace ni
        en qué orden; hace legible el recorrido y deja el aviso por correo en
        un solo sitio. Es la única divergencia de forma del bloque.
        """
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(self.sftp_host, self.sftp_port, self.sftp_user,
                           self.sftp_password, timeout=20)
            sftp = client.open_sftp()

            path_to_write_to = self.sftp_path
            _logger.debug('sftp remote path: %s', path_to_write_to)
            try:
                sftp.chdir(path_to_write_to)
            except IOError:
                # Crea el árbol de directorios si no existe — ≙ ``:170-183``.
                current_directory = ''
                for element in path_to_write_to.split('/'):
                    current_directory += element + '/'
                    try:
                        sftp.chdir(current_directory)
                    except IOError:
                        _logger.info(
                            "(Part of the) path didn't exist. Creating it now at %s",
                            current_directory)
                        sftp.mkdir(current_directory, 777)
                        sftp.chdir(current_directory)
            sftp.chdir(path_to_write_to)

            # Sube lo que falte — ≙ ``:186-203``.
            for entry in os.listdir(self.folder):
                if self.name not in entry:
                    continue
                fullpath = os.path.join(self.folder, entry)
                if not os.path.isfile(fullpath):
                    continue
                try:
                    sftp.stat(os.path.join(path_to_write_to, entry))
                    _logger.debug(
                        'File %s already exists on the remote FTP Server '
                        '------ skipped', fullpath)
                except IOError:
                    try:
                        sftp.put(fullpath, os.path.join(path_to_write_to, entry))
                        _logger.info('Copying File %s ------ success', fullpath)
                    except Exception as err:  # noqa: BLE001 — un archivo no corta el resto
                        _logger.critical(
                            "We couldn't write the file to the remote server. "
                            'Error: %s', str(err))

            # Purga los caducados del remoto — ≙ ``:206-227``.
            sftp.chdir(path_to_write_to)
            now = datetime.datetime.now()
            for entry in sftp.listdir(path_to_write_to):
                if self.name not in entry:
                    continue
                fullpath = os.path.join(path_to_write_to, entry)
                createtime = datetime.datetime.fromtimestamp(
                    sftp.stat(fullpath).st_mtime)
                if (now - createtime).days >= self.days_to_keep_sftp:
                    if '.dump' in entry or '.zip' in entry:
                        _logger.info(
                            'Delete too old file from SFTP servers: %s', entry)
                        sftp.unlink(entry)
            sftp.close()
            client.close()
        except Exception as exc:  # noqa: BLE001 — ≙ el except ancho de ``:228``
            _logger.debug("Exception! We couldn't back up to the FTP server..")
            if self.send_mail_sftp_fail:
                self._notify_sftp_failure(exc)

    def _notify_sftp_failure(self, exc):
        """Avisa por correo del fallo de la copia remota — ≙ ``:232-247``.

        DIVERGENCIA de mecanismo: la fuente arma el mensaje con
        ``ir.mail_server.build_email``/``send_email``; aquí el canal es
        ``dispatch_email`` (el patrón síncrono del proyecto, con reintento
        vía ``EmailTask``). El remitente sale de ``mail.catchall.domain``
        exactamente como allá, leído de ``SystemParameter`` — el espejo de
        ``ir.config_parameter``.

        Nunca re-lanza: un fallo al avisar no debe enmascarar el fallo que
        avisa (mismo criterio que ``_notify_backup_failed`` en la capa DRF).
        """
        try:
            catchall = SystemParameter.get_param('mail.catchall.domain', '')
            sender = 'auto_backup@%s' % catchall if catchall else None
            dispatch_email(
                subject='Backup from %s(%s) failed' % (self.host, self.sftp_host),
                message=(
                    'Dear,\n\nThe backup for the server ' + (self.host or '') +
                    ' (IP: ' + (self.sftp_host or '') + ') failed. Please check '
                    'the following details:\n\nIP address SFTP server: ' +
                    (self.sftp_host or '') + '\nUsername: ' + (self.sftp_user or '') +
                    '\n\nError details: ' + str(exc) + '\n\nWith kind regards'
                ),
                from_email=sender,
                recipient_list=[self.email_to_notify] if self.email_to_notify else [],
            )
        except Exception:  # noqa: BLE001 — ≙ el ``except Exception: pass`` de ``:246``
            _logger.exception('No se pudo despachar el aviso de fallo de SFTP.')

    def _remove_old_local_backups(self):
        """Borra los respaldos locales caducados — ≙ ``:249-275``.

        Extraído del cuerpo de ``schedule_backup`` por la misma razón que
        ``_copy_to_sftp``. Conserva la asimetría de la fuente: si hay fila de
        detalle se borra la fila (y su ``delete()`` retira el archivo), y si
        no la hay se borra el archivo suelto.
        """
        now = datetime.datetime.now()
        for entry in os.listdir(self.folder):
            fullpath = os.path.join(self.folder, entry)
            if self.name not in fullpath:
                continue
            createtime = datetime.datetime.fromtimestamp(os.stat(fullpath).st_ctime)
            if (now - createtime).days < self.days_to_keep:
                continue
            if os.path.isfile(fullpath) and ('.dump' in entry or '.zip' in entry):
                _logger.info('Delete local out-of-date file: %s', fullpath)
                detail = DbBackupDetails.objects.filter(file_path=fullpath).first()
                if detail is not None:
                    detail.delete()
                else:
                    os.remove(fullpath)

    def _take_dump(self, db_name, stream, model, backup_format='zip'):
        """Vuelca ``db_name`` en ``stream`` — ≙ ``:283``.

        La fuente duplica a propósito ``service/db.py::dump_db`` para **no**
        pasar por ``check_db_management_enabled``, y lo argumenta: así el
        operador puede desactivar el gestor de bases y aun así tener
        respaldos programados. Ese argumento se sostiene igual aquí, así que
        el porte reusa las piezas de ``service.db`` (``_pg_env``,
        ``database_exists``) pero **no** ``dump_database``, que sí llama a
        ``ensure_management_enabled()``.

        Su guarda de autorización se porta entera: sólo el usuario del cron
        puede volcar, y sólo sobre ``db.backup``.
        """
        cron = IrCron.objects.filter(
            ir_actions_server__model_name='auto_backup.DbBackup',
            ir_actions_server__method_name='schedule_backup',
        ).first()
        cron_user_id = cron.user_id if cron is not None else None
        current_uid = get_current_uid()
        # DIVERGENCIA que CIERRA un hueco, no que lo abre (:ref:`h-api-766`).
        # La comparación de la fuente —``cron_user_id != self.env.user.id``—
        # basta allá porque sus dos lados son enteros: una petición siempre
        # trae usuario y ``user_id`` del cron es ``required=True``. Aquí los
        # dos pueden ser ``None``, y ``None != None`` es falso: transliterada,
        # la guarda deja pasar a un llamador **sin autenticar** contra un cron
        # sin usuario. Se exige que ambos existan antes de compararlos.
        if (type(self)._name != 'db.backup'
                or cron_user_id is None or current_uid is None
                or cron_user_id != current_uid):
            _logger.error('Unauthorized database operation. Backups should only '
                          'be available from the cron job.')
            raise AccessDenied()

        _logger.info('DUMP DB: %s format %s', db_name, backup_format)
        if not database_exists(db_name):
            raise ValueError('la base %r no existe' % (db_name,))

        cmd = ['pg_dump', '--no-owner', db_name]
        env = _pg_env()
        if backup_format == 'zip':
            with tempfile.TemporaryDirectory() as dump_dir:
                sql_path = os.path.join(dump_dir, 'dump.sql')
                manifest_path = os.path.join(dump_dir, 'manifest.json')
                with open(manifest_path, 'w') as handle:
                    with connections[DEFAULT_DB_ALIAS].cursor() as cursor:
                        json.dump(self._dump_db_manifest(cursor), handle, indent=4)
                cmd.insert(-1, '--file=' + sql_path)
                subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.STDOUT, check=True)
                # ≙ ``zip_dir(dump_dir, stream, include_dir=False)``. Sin la
                # rama ``filestore/`` de la fuente: aquí los binarios de
                # ``ir.attachment`` viven en la propia base (``datas``), así
                # que el volcado SQL ya es completo — la misma divergencia
                # que ``service/db.py::dump_database`` declara.
                with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.write(manifest_path, 'manifest.json')
                    archive.write(sql_path, 'dump.sql')
                return None
        cmd.insert(-1, '--format=c')
        process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, _stderr = process.communicate()
        if stream:
            stream.write(stdout)
            return None
        return stdout

    def _dump_db_manifest(self, cursor):
        """El manifiesto que acompaña al volcado ``zip`` — ≙ ``:325``.

        ``latest_version`` de la fuente → ``version``: ``ir.module.module``
        aquí no declara la primera. El resto sale de ``src/release.py``, el
        espejo de ``odoo/release.py``.
        """
        # ``cr._obj.connection.server_version`` de la fuente es **psycopg2**;
        # con psycopg 3 el dato vive en ``connection.info`` y el atributo
        # plano no existe — transliterado, el manifiesto revienta con
        # ``AttributeError`` en cada volcado ``zip`` (:ref:`h-api-766`).
        pg_version = '%d.%d' % divmod(
            cursor.connection.info.server_version / 100, 100)
        modules = dict(
            IrModule.objects.filter(state='installed').values_list('name', 'version')
        )
        return {
            'odoo_dump': '1',
            'db_name': connections[DEFAULT_DB_ALIAS].settings_dict['NAME'],
            'version': release.version,
            'version_info': release.version_info,
            'major_version': release.major_version,
            'pg_version': pg_version,
            'modules': modules,
        }

    def action_run_cron(self):
        """Dispara ahora el cron del respaldo — ≙ ``:350``.

        ``cron.method_direct_trigger()`` de la fuente equivale aquí a adquirir
        el job con ``include_not_ready=True`` y correrlo; ``ir_cron.py:384``
        ya declara esa equivalencia. Devuelve ``True`` si había job que
        disparar, ``False`` si no — la misma señal que la fuente.
        """
        cron = IrCron.objects.filter(
            ir_actions_server__model_name='auto_backup.DbBackup',
            ir_actions_server__method_name='schedule_backup',
        ).first()
        if cron is None:
            return False
        with transaction.atomic():
            job = IrCron._acquire_one_job(cron.pk, include_not_ready=True)
            if job is None:
                return False
            job._run_job()
        return True
