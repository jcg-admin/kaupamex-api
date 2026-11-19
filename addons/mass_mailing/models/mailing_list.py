"""``mailing.list`` — lista de correo (Odoo ``mass_mailing``).

Portacion fiel de ``mass_mailing/models/mailing_list.py`` (``mailing.list``,
Odoo 19 community, LGPL-3): una lista de contactos a la que se dirige un envio
masivo. La membresia contacto↔lista vive en ``mailing.subscription`` (M2M con
datos: opt-out por lista). Reemplaza el concepto implicito de "audiencia" del
addon de proyecto ``newsletter`` (disuelto aqui, hogar fiel).
"""

import fields
import models

from addons.base.models import TimeStampedModel


class MailingList(models.BaseModel, TimeStampedModel):
    """``mailing.list`` — lista de correo para envios masivos."""

    #: ≙ la cabecera de la fuente
    #: (``odoo19c: addons/mass_mailing/models/mailing_list.py:12-18``). La
    #: fuente asigna ``_order`` dos veces y gana la segunda.
    _name = 'mailing.list'
    _description = 'Mailing List'
    _mailing_enabled = True
    _order = 'create_date DESC'
    _disable_data_merge = True

    name = fields.Char(
        max_length=255,
        help_text='Nombre de la lista (Odoo name).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Archivar sin borrar (Odoo active).',
    )
    is_public = fields.Boolean(
        default=False,
        help_text=(
            'Visible en el portal de gestion de suscripciones (Odoo'
            ' is_public).'
        ),
    )

    class Meta:
        db_table = 'mailing_list'
        ordering = ['name', 'id']
        verbose_name = 'Lista de correo'
        verbose_name_plural = 'Listas de correo'

    def __str__(self) -> str:
        return self.name
