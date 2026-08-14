"""``mail.tracking.value`` — auditoria de cambio de campo (Odoo ``mail``).

Portacion fiel de ``MailTracking``
(``scratchpad/odoo19x/addons/mail/models/mail_tracking_value.py:10-35``, Odoo 19;
identico en 18) — el registro del valor anterior y nuevo de un campo rastreado
cuando cambia, adjunto a un ``mail.message`` de notificacion en el chatter del
documento. Parte de la familia ``mail`` (SOL-096).

Fuente Odoo community (LGPL-3): copia + adaptacion con atribucion.

- ``message`` ← ``mail_message_id`` (Odoo, ``required``, ``ondelete='cascade'``).
- ``field`` ← ``field_id`` (Odoo ``ir.model.fields``): este monolito NO porta
  ``ir.model.fields`` (H-BASE-08), asi que el campo rastreado se guarda como
  nombre plano (``Char``) + ``field_desc``, mismo criterio que ``mail.message.model``.
- ``currency`` ← ``currency_id`` (Odoo ``res.currency``) → ``base.ResCurrency``.
- Los pares ``old_value_*`` / ``new_value_*`` (integer/float/char/text/datetime)
  son fieles uno a uno a Odoo; el tipo se elige por ``field_type``.
"""
import fields
import models
from addons.base.models import TimeStampedModel


class MailTrackingValue(TimeStampedModel):
    """``mail.tracking.value`` — valor anterior/nuevo de un campo rastreado."""

    message = fields.Many2one(
        'mail.MailMessage', on_delete=models.CASCADE,
        related_name='tracking_value_ids',
        help_text='Mensaje de notificacion asociado (Odoo mail_message_id).',
    )
    field = fields.Char(
        max_length=128,
        help_text='Nombre del campo rastreado (Odoo field_id.name; plano, sin ir.model.fields).',
    )
    field_desc = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Etiqueta legible del campo (Odoo field_id.field_description).',
    )
    field_type = fields.Char(
        max_length=32, blank=True, default='char',
        help_text='Tipo del campo: char/integer/float/text/datetime/monetary/boolean (Odoo field_type).',
    )
    currency = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        help_text='Moneda para campos monetarios (Odoo currency_id).',
    )
    old_value_integer = fields.Integer(null=True, blank=True, help_text='Odoo old_value_integer.')
    old_value_float = fields.Float(null=True, blank=True, help_text='Odoo old_value_float.')
    old_value_char = fields.Char(max_length=255, blank=True, default='', help_text='Odoo old_value_char.')
    old_value_text = fields.Text(blank=True, default='', help_text='Odoo old_value_text.')
    old_value_datetime = fields.Datetime(null=True, blank=True, help_text='Odoo old_value_datetime.')
    new_value_integer = fields.Integer(null=True, blank=True, help_text='Odoo new_value_integer.')
    new_value_float = fields.Float(null=True, blank=True, help_text='Odoo new_value_float.')
    new_value_char = fields.Char(max_length=255, blank=True, default='', help_text='Odoo new_value_char.')
    new_value_text = fields.Text(blank=True, default='', help_text='Odoo new_value_text.')
    new_value_datetime = fields.Datetime(null=True, blank=True, help_text='Odoo new_value_datetime.')

    # tipo de campo -> sufijo de columna de valor (Odoo _get_field_value_type)
    _TYPE_SUFFIX = {
        'integer': 'integer', 'boolean': 'integer', 'many2one': 'integer',
        'float': 'float', 'monetary': 'float',
        'char': 'char', 'selection': 'char',
        'text': 'text', 'html': 'text',
        'date': 'datetime', 'datetime': 'datetime',
    }

    class Meta:
        db_table = 'mail_tracking_value'
        ordering = ['id']
        verbose_name = 'Valor rastreado'
        verbose_name_plural = 'Valores rastreados'
        indexes = [
            models.Index(fields=['message'], name='mail_trackval_message_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.field}: {self.get_old_value()} → {self.get_new_value()}'

    @classmethod
    def _value_suffix(cls, field_type: str) -> str:
        return cls._TYPE_SUFFIX.get(field_type or 'char', 'char')

    def set_values(self, old, new):
        """Coloca ``old``/``new`` en las columnas del tipo (Odoo ``_create_tracking_values``)."""
        suffix = self._value_suffix(self.field_type)
        if suffix in ('char',):
            self.old_value_char = '' if old is None else str(old)[:255]
            self.new_value_char = '' if new is None else str(new)[:255]
        elif suffix == 'text':
            self.old_value_text = '' if old is None else str(old)
            self.new_value_text = '' if new is None else str(new)
        elif suffix == 'integer':
            self.old_value_integer = None if old is None else int(old)
            self.new_value_integer = None if new is None else int(new)
        elif suffix == 'float':
            self.old_value_float = None if old is None else float(old)
            self.new_value_float = None if new is None else float(new)
        elif suffix == 'datetime':
            self.old_value_datetime = old
            self.new_value_datetime = new

    def get_old_value(self):
        return getattr(self, f'old_value_{self._value_suffix(self.field_type)}')

    def get_new_value(self):
        return getattr(self, f'new_value_{self._value_suffix(self.field_type)}')
