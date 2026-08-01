"""``ir.logging`` — log de aplicación fiel a Odoo (DEC-08, slice 2 de la
disolución de ``core/``, iniciativa ``adoptar-arquitectura-server-service-odoo``).

Portación fiel de ``IrLogging``
(``scratchpad/odoo19x/odoo/addons/base/models/ir_logging.py``, Odoo 19): el
modelo que recibe cada entrada de log ruteada por el framework de logging
(equivalente Odoo del handler ``--log-db``). Reemplaza a ``core.models.AppLog``
(el modelo previo de esta app, adaptado de ``StatusLog`` de django-db-logger
0.1.13). ``AppLog`` queda eliminado de ``core`` en este mismo slice; sus filas
se copian aquí de forma no destructiva vía migración de datos (ver
``addons/base/migrations/0007_copiar_applog_a_irlogging.py`` y
``core/migrations/0002_eliminar_applog.py``).

Correspondencia de campos Odoo -> Django (mapeo fiel; cada divergencia respecto
a Odoo o al ``AppLog`` previo se documenta explícitamente):

- ``name`` (Char, required) -> ``name``: nombre del logger Python que emitió
  el registro (antes ``AppLog.logger_name``).
- ``type`` (Selection client/server, required, index) -> ``type``: nuestro
  handler solo corre en el backend Django, así que siempre escribe
  ``'server'``. Se preserva la opción ``'client'`` por fidelidad al modelo de
  Odoo aunque hoy no exista un canal de logging de cliente equivalente al JS
  del framework web de Odoo.
- ``dbname`` (Char, index) -> ``dbname``: nombre de la base de datos activa al
  momento del log; Odoo lo usa para distinguir instancias que comparten una
  única tabla de log (``--log-db``). El ``DatabaseLogHandler`` lo puebla desde
  ``connection.settings_dict['NAME']``.
- ``level`` (Char, index, sin restricción de valores en Odoo) -> ``level``:
  **divergencia deliberada** — se preserva la validación con ``choices`` que
  ya tenía ``AppLog`` (DEBUG/INFO/WARNING/ERROR/CRITICAL) porque
  ``purge_logs`` (DEC-LOG-05) filtra por estos niveles exactos y una columna
  sin restricción arriesgaría silenciosamente esa política de retención.
- ``message`` (Text, required) -> ``message`` (antes ``AppLog.msg``):
  **divergencia** — se mantiene ``blank=True, default=''`` en vez de forzar
  no-vacío a nivel de validación, para no romper el comportamiento previo del
  handler ante mensajes vacíos. La columna SQL sigue siendo ``NOT NULL``
  (falta de ``null=True``), igual que en Odoo.
- ``path`` / ``func`` / ``line`` (Char, required en Odoo — sitio de la
  llamada) -> mismos nombres; **divergencia** — se relajan a
  ``blank=True, default=''`` porque no siempre hay call-site resoluble
  (algunos management commands). A diferencia de ``AppLog`` (que no los
  tenía), el ``DatabaseLogHandler`` los puebla desde el propio ``LogRecord``
  (``pathname``/``funcName``/``lineno``) cuando están disponibles — esto hace
  la portación *más* fiel a Odoo que el modelo previo.
- ``create_uid`` / ``write_uid`` (Integer, Odoo) -> **omitidos**. Odoo mismo
  documenta que son manuales por bypass del ORM (ver comentario en la fuente
  portada); aquí no hay un actor humano en un log técnico — el join a "en qué
  request" se hace vía ``correlation_id`` -> ``RequestLog.user``
  (DEC-LOG-07), no vía un ``create_uid`` propio.
- ``create_date`` / ``write_date`` (Datetime) -> ``created_at`` / ``updated_at``
  (heredados de ``AppendOnlyModel``/``TimeStampedModel``, DEC-09).

Columnas propias (NO existen en Odoo ``ir.logging``, necesarias para el
pipeline de logging de este proyecto, DEC-LOG-07):

- ``correlation_id``: une esta fila con ``RequestLog`` / ``BusinessEvent`` de
  la misma request HTTP. Odoo no tiene un concepto de correlación de request
  a nivel de ``ir.logging``.
- ``trace``: traceback ya redactado (Nivel 1, DEC-LOG-03) cuando el
  ``LogRecord`` trae ``exc_info``. Odoo no separa el traceback de
  ``message``; se mantiene separado aquí por compatibilidad con el
  consumidor (``AdminLogsView`` / ``AdminLogsPage``, UC-ADM-06), que ya
  distinguía mensaje corto vs. traza completa.

Append-only (SOL-011, DEC-LOG-05): hereda ``AppendOnlyModel`` — INSERT
permitido, UPDATE/DELETE de instancia bloqueados (``PermissionError``); la
purga por retención (``purge_logs``) usa ``QuerySet.delete()`` en bulk, que no
pasa por el guard de instancia.
"""
from django.db import models

from addons.base.models.append_only_mixin import AppendOnlyModel


class IrLogging(AppendOnlyModel):
    """``ir.logging`` — entrada de log técnico (ver docstring del módulo)."""

    TYPE_CLIENT = 'client'
    TYPE_SERVER = 'server'
    TYPE_CHOICES = [
        (TYPE_CLIENT, 'Client'),
        (TYPE_SERVER, 'Server'),
    ]

    LEVEL_DEBUG = 'DEBUG'
    LEVEL_INFO = 'INFO'
    LEVEL_WARNING = 'WARNING'
    LEVEL_ERROR = 'ERROR'
    LEVEL_CRITICAL = 'CRITICAL'
    LEVEL_CHOICES = [
        (LEVEL_DEBUG, 'Debug'),
        (LEVEL_INFO, 'Info'),
        (LEVEL_WARNING, 'Warning'),
        (LEVEL_ERROR, 'Error'),
        (LEVEL_CRITICAL, 'Critical'),
    ]

    name = models.CharField(max_length=255, db_index=True)
    type = models.CharField(
        max_length=8, choices=TYPE_CHOICES, default=TYPE_SERVER, db_index=True)
    dbname = models.CharField(max_length=255, blank=True, default='', db_index=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, db_index=True)
    message = models.TextField(blank=True, default='')
    path = models.CharField(max_length=255, blank=True, default='')
    func = models.CharField(max_length=255, blank=True, default='')
    line = models.CharField(max_length=32, blank=True, default='')

    # Columnas propias (no presentes en Odoo ir.logging) — ver docstring del
    # módulo, sección "Columnas propias" (DEC-LOG-07).
    correlation_id = models.CharField(max_length=32, db_index=True, blank=True, default='')
    trace = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'ir_logging'
        ordering = ['-id']
        verbose_name = 'Logging'
        verbose_name_plural = 'Logging'
        indexes = [
            models.Index(fields=['-created_at'], name='ir_logging_created_idx'),
        ]

    def __str__(self):
        return f'{self.level} {self.name}: {self.message[:60]}'
