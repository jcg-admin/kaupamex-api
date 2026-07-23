"""``mail.message.subtype`` — subtipos de mensaje (Odoo ``mail``).

Portacion fiel de ``MailMessageSubtype``
(``scratchpad/odoo19x/addons/mail/models/mail_message_subtype.py``, Odoo 19;
identico en 18) — la clasificacion de los mensajes del chatter (p. ej.
"Discussions", "Note", o subtipos de negocio como "Order Confirmed") que
gobierna a que seguidores se notifica. Parte de la familia ``mail`` (SOL-096).

Fuente Odoo community (LGPL-3): copia + adaptacion con atribucion. Los campos
de solo-UI de Odoo (``hidden`` de la vista, ``subtype_xmlid`` de datos XML) se
conservan como datos planos; la mecanica de notificacion por subtipo la
consume ``mail.thread`` (``message_post`` + ``mail.followers.subtype_ids``).
"""
import fields
import models
from addons.base.models import TimeStampedModel


class MailMessageSubtype(TimeStampedModel):
    """``mail.message.subtype`` — subtipo de un mensaje del chatter."""

    name = fields.Char(
        max_length=255,
        help_text='Nombre del subtipo (Odoo name), p. ej. "Discussions".',
    )
    description = fields.Text(
        blank=True, default='',
        help_text='Descripcion mostrada en la notificacion (Odoo description).',
    )
    internal = fields.Boolean(
        default=False,
        help_text=(
            'Solo empleados internos reciben este subtipo (Odoo internal). '
            'Los subtipos internos no se envian a seguidores del portal.'
        ),
    )
    parent = fields.Many2one(
        'mail.MailMessageSubtype', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='children',
        help_text='Subtipo padre para relaciones cross-modelo (Odoo parent_id).',
    )
    res_model = fields.Char(
        max_length=128, blank=True, default='',
        help_text=(
            'Modelo al que aplica el subtipo, p. ej. "orders.Order" (Odoo '
            'res_model). Vacio = aplica a todos los modelos.'
        ),
    )
    relation_field = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Campo de relacion para auto-suscripcion cross-modelo (Odoo relation_field).',
    )
    default = fields.Boolean(
        default=True,
        help_text='Activado por defecto al seguir un registro (Odoo default).',
    )
    sequence = fields.Integer(
        default=1,
        help_text='Orden de despliegue (Odoo sequence).',
    )
    hidden = fields.Boolean(
        default=False,
        help_text='Oculto en la vista de preferencias del seguidor (Odoo hidden).',
    )

    class Meta:
        db_table = 'mail_message_subtype'
        ordering = ['sequence', 'id']
        verbose_name = 'Subtipo de mensaje'
        verbose_name_plural = 'Subtipos de mensaje'
        indexes = [
            models.Index(fields=['res_model'], name='mail_subtype_res_model_idx'),
        ]

    def __str__(self) -> str:
        return self.name
