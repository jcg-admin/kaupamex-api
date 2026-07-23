"""``mail.followers`` — seguidores de un registro (Odoo ``mail``).

Portacion fiel de ``Followers``
(``scratchpad/odoo19x/addons/mail/models/mail_followers.py:20-33``, Odoo 19;
identico en 18) — la relacion polimorfica (``res_model``+``res_id``) que declara
que un party sigue un documento y con que subtipos, gobernando a quien se
notifica cuando se publica un mensaje. Parte de la familia ``mail`` (SOL-096).

Fuente Odoo community (LGPL-3): copia + adaptacion con atribucion.

- ``partner`` ← ``partner_id`` (Odoo ``res.partner``): party = ``users.IdentityUser``
  (DEC-SALE-01), FK a ``AUTH_USER_MODEL``.
- ``subtype_ids`` (M2M ``mail.message.subtype``): subtipos que el seguidor
  recibe; fiel al Odoo ``subtype_ids``.
- La unicidad ``(res_model, res_id, partner)`` replica el ``_sql_constraints``
  ``mail_followers_res_partner_res_model_id_uniq`` de Odoo.
"""
from django.conf import settings

import fields
import models
from addons.base.models import TimeStampedModel


class MailFollowers(TimeStampedModel):
    """``mail.followers`` — un party sigue un registro polimorfico."""

    res_model = fields.Char(
        max_length=128,
        help_text='Modelo del registro seguido, p. ej. "support.SupportTicket" (Odoo res_model).',
    )
    res_id = fields.Integer(
        null=True, blank=True,
        help_text='ID del registro seguido (Odoo res_id, Integer plano).',
    )
    partner = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='followed_records',
        help_text='Party seguidor (Odoo partner_id → res.partner; party = IdentityUser).',
    )
    subtype_ids = fields.Many2many(
        'mail.MailMessageSubtype', blank=True, related_name='followers',
        help_text='Subtipos que este seguidor recibe (Odoo subtype_ids).',
    )

    class Meta:
        db_table = 'mail_followers'
        ordering = ['id']
        verbose_name = 'Seguidor'
        verbose_name_plural = 'Seguidores'
        constraints = [
            models.UniqueConstraint(
                fields=['res_model', 'res_id', 'partner'],
                name='mail_followers_res_partner_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['res_model', 'res_id'], name='mail_followers_record_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.res_model}#{self.res_id} ← {self.partner_id}'
