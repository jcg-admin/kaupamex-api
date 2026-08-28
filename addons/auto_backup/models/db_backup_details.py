"""``db.backup.details`` — cada ejecución del respaldo, con su archivo.

Adaptación de ``app_auto_backup/models/db_backup_details.py``
(``odoo-tools@622ddc2a``, ``18.x/app-odoo-18.0``, **LGPL-3**).

**Este archivo se llamaba ``backup_record.py`` y su clase ``BackupRecord``.**
Los dos nombres eran propios, sobre la premisa —falsa— de que la referencia
no tenía addon de respaldo (:ref:`h-api-763`). Medida la contraparte, el
modelo es el mismo concepto que ``db.backup.details``: una fila por corrida,
con el archivo que produjo. Se renombra clase, archivo y tabla para que la
comparación símbolo a símbolo tenga con qué alinearse — la segunda cláusula
de ``atributos-de-clase-de-modelo.md`` (el **sitio** del archivo se lee
contra la raíz espejada, y ``models/backup_record.py`` no existe allá).

Cobertura contra la fuente — 3 atributos, 4 campos, 3 métodos
==============================================================

.. list-table::
   :header-rows: 1
   :widths: 26 16 58

   * - Símbolo
     - Desenlace
     - Detalle
   * - ``_name``/``_description``/``_order``
     - PORTADOS
     - los tres, verbatim. Antes: **0 de 3**.
   * - ``name``
     - PORTADO
     - era ``filename``; se restituye el nombre de la fuente.
   * - ``file_path``
     - PORTADO
     - **ausente** hasta ahora — sin él ``unlink`` no tiene qué borrar.
   * - ``url``
     - PORTADO
     - era ``download_url`` (``URLField``). Vuelve a ``Char``: el valor que
       la fuente escribe es ``/dbbackup/download/<ruta>``, una **ruta
       relativa** que un ``URLField`` rechaza en ``full_clean()``.
   * - ``db_backup_id``
     - PORTADO
     - **ausente** hasta ahora — la ejecución no sabía de qué configuración
       venía. ``related_name='backup_details_ids'`` es el One2many del otro
       lado.
   * - ``action_download_file``
     - PORTADO
     - devuelve el descriptor ``ir.actions.act_url``, la forma de la fuente;
       el árbol ya tiene ``IrActionsActUrl`` y cuatro precedentes que
       devuelven ese mismo dict.
   * - ``unlink``
     - PORTADO
     - ``delete()`` **es** el hook equivalente en este stack. El guion bajo
       del nombre no aplica —``unlink`` es público allá— y el nombre cambia
       porque cambia el mecanismo, igual que
       ``hr_departure_reason.py::delete()``.
   * - ``action_remove_file``
     - PORTADO
     - verbatim; llama a ``delete()``.

Cuatro campos son **nuestros**, no de la fuente
------------------------------------------------

``type``, ``status``, ``size_bytes`` y ``error_detail`` no tienen contraparte
en ``db.backup.details``, y **se conservan**: son lo que UC-ADM-05 lista en
el historial del operador (manual contra programado, en curso contra
terminado, y el detalle del fallo). La fuente no los necesita porque su
historial vive en la vista de Odoo; el nuestro es un endpoint REST.
"""
import logging
import os

import fields
import models
from exceptions import UserError
from tools.translate import _

from addons.base.models import TimeStampedModel

_logger = logging.getLogger(__name__)


class DbBackupDetails(TimeStampedModel):
    """``db.backup.details`` — una ejecución de respaldo y su archivo."""

    # Atributos de clase de modelo — los tres que la fuente declara
    # (``app_auto_backup/models/db_backup_details.py:10-12``), verbatim.
    _name = 'db.backup.details'
    _description = 'Database Backup Details'
    _order = 'id desc'

    # --- Vocabulario propio (sin contraparte en la fuente) ---
    TYPE_AUTO = 'AUTO'
    TYPE_MANUAL = 'MANUAL'
    TYPE_CHOICES = [
        (TYPE_AUTO, 'Automático'),
        (TYPE_MANUAL, 'Manual'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_OK = 'OK'
    STATUS_ERROR = 'ERROR'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_OK, 'Completado'),
        (STATUS_ERROR, 'Error'),
    ]

    # --- Los cuatro campos de la fuente ---
    name = fields.Char(
        'Name', blank=True, default='',
        help_text='Nombre del archivo de respaldo (Odoo name).',
    )
    file_path = fields.Char(
        'File Path', blank=True, default='',
        help_text='Ruta absoluta del archivo en disco (Odoo file_path).',
    )
    url = fields.Char(
        'URL', blank=True, default='',
        help_text=(
            'Ruta de descarga (Odoo url). Es relativa —'
            '/dbbackup/download/<ruta>—, no una URL absoluta.'
        ),
    )
    db_backup_id = fields.Many2one(
        'auto_backup.DbBackup', on_delete=models.CASCADE,
        null=True, blank=True, related_name='backup_details_ids',
        verbose_name='Database Backup',
        help_text='Configuración que produjo esta corrida (Odoo db_backup_id).',
        db_column='db_backup_id',
    )

    # --- Campos propios: el historial que UC-ADM-05 lista ---
    type = fields.Selection(
        'Tipo', max_length=10, choices=TYPE_CHOICES, default=TYPE_AUTO)
    status = fields.Selection(
        'Estado', max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    error_detail = fields.Text(blank=True, default='')

    class Meta:
        # Derivado de ``_name`` — ``check_table_matches_name()`` lo verifica.
        db_table = 'db_backup_details'
        # Derivado de ``_order = 'id desc'``.
        ordering = ['-id']
        verbose_name = 'Respaldo'
        verbose_name_plural = 'Respaldos'

    def __str__(self):
        return f'{self.name or self.pk} {self.status}'

    def action_download_file(self):
        """Descriptor de descarga — ≙ ``:20``."""
        if not self.file_path or not self.url:
            raise UserError(_('File Path or URL not found.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.url,
            'target': 'new',
        }

    def delete(self, *args, **kwargs):
        """Retira el archivo de disco y luego la fila — ≙ ``unlink`` (``:31``).

        El ``except`` ancho y silencioso es el de la fuente: un archivo ya
        borrado a mano no debe impedir que la fila se retire. Se conserva el
        comportamiento y se añade la traza, que allá no hay — un ``pass``
        mudo esconde un permiso mal puesto sobre el directorio de respaldos.
        """
        try:
            if self.file_path and os.path.exists(self.file_path):
                os.remove(self.file_path)
        except OSError:
            _logger.warning('No se pudo retirar el archivo de respaldo %s',
                            self.file_path, exc_info=True)
        return super().delete(*args, **kwargs)

    def action_remove_file(self):
        """Borra la fila (y con ella el archivo) — ≙ ``:39``."""
        return self.delete()
