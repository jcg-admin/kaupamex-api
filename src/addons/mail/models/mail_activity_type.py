"""``mail.activity.type`` — tipo de actividad (Odoo ``mail``).

Portacion fiel de ``MailActivityType``
(``scratchpad/odoo19x/addons/mail/models/mail_activity_type.py:20-76``, Odoo 19;
identico en 18) — la plantilla de una actividad planificable sobre el chatter
(p. ej. "Llamada", "Correo", "Subir documento") con su plazo por defecto y
encadenamiento. Parte de la familia ``mail`` (SOL-096).

Fuente Odoo community (LGPL-3): copia + adaptacion con atribucion.
"""
import fields
import models
from addons.base.models import TimeStampedModel


class MailActivityType(TimeStampedModel):
    """``mail.activity.type`` — plantilla de una actividad del chatter."""

    DELAY_DAYS = 'days'
    DELAY_WEEKS = 'weeks'
    DELAY_MONTHS = 'months'
    DELAY_UNIT_CHOICES = [
        (DELAY_DAYS, 'days'),
        (DELAY_WEEKS, 'weeks'),
        (DELAY_MONTHS, 'months'),
    ]
    DELAY_FROM_CHOICES = [
        ('current_date', 'after completion date'),
        ('previous_activity', 'after previous activity deadline'),
    ]
    CHAINING_SUGGEST = 'suggest'
    CHAINING_TRIGGER = 'trigger'
    CHAINING_TYPE_CHOICES = [
        (CHAINING_SUGGEST, 'Suggest Next Activity'),
        (CHAINING_TRIGGER, 'Trigger Next Activity'),
    ]
    CATEGORY_CHOICES = [
        ('default', 'None'),
        ('upload_file', 'Upload Document'),
        ('phonecall', 'Phonecall'),
    ]

    name = fields.Char(max_length=255, help_text='Nombre del tipo (Odoo name).')
    summary = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Resumen por defecto de la actividad (Odoo summary).',
    )
    sequence = fields.Integer(default=10, help_text='Orden (Odoo sequence).')
    active = fields.Boolean(default=True, help_text='Odoo active.')
    delay_count = fields.Integer(
        default=0, help_text='Cantidad de plazo por defecto (Odoo delay_count).',
    )
    delay_unit = fields.Selection(
        max_length=8, choices=DELAY_UNIT_CHOICES, default=DELAY_DAYS,
        help_text='Unidad del plazo (Odoo delay_unit).',
    )
    delay_from = fields.Selection(
        max_length=20, choices=DELAY_FROM_CHOICES, default='previous_activity',
        help_text='Origen del plazo (Odoo delay_from).',
    )
    icon = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Icono FontAwesome, p. ej. fa-tasks (Odoo icon).',
    )
    decoration_type = fields.Selection(
        max_length=8, choices=[('warning', 'Alert'), ('danger', 'Error')],
        blank=True, default='',
        help_text='Decoracion visual (Odoo decoration_type).',
    )
    res_model = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Modelo al que aplica, p. ej. "orders.Order"; vacio = todos (Odoo res_model).',
    )
    chaining_type = fields.Selection(
        max_length=8, choices=CHAINING_TYPE_CHOICES, default=CHAINING_SUGGEST,
        help_text='Encadenamiento a la siguiente actividad (Odoo chaining_type).',
    )
    category = fields.Selection(
        max_length=16, choices=CATEGORY_CHOICES, default='default',
        help_text='Categoria de accion (Odoo category).',
    )
    default_note = fields.Html(
        blank=True, default='',
        help_text='Nota por defecto (Odoo default_note).',
    )

    class Meta:
        db_table = 'mail_activity_type'
        ordering = ['sequence', 'id']
        verbose_name = 'Tipo de actividad'
        verbose_name_plural = 'Tipos de actividad'

    def __str__(self) -> str:
        return self.name
