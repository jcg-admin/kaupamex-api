"""``mailing.subscription`` — membresia contacto↔lista (Odoo ``mass_mailing``).

Portacion fiel de ``mass_mailing/models/mailing_subscription.py``
(``mailing.subscription``, antes ``mailing.contact.subscription``): la tabla
intermedia con datos del M2M ``mailing.contact`` ↔ ``mailing.list``. El opt-out
es **por lista** (un contacto puede seguir una lista y salirse de otra), fiel a
Odoo — a diferencia del opt-out global del ``NewsletterSubscriber`` de proyecto.
"""
import fields
import models

from addons.base.models import TimeStampedModel

from .mailing_contact import MailingContact
from .mailing_list import MailingList


class MailingSubscription(TimeStampedModel):
    """``mailing.subscription`` — contacto suscrito a una lista, con opt-out."""

    contact = fields.Many2one(
        MailingContact, on_delete=models.CASCADE,
        related_name='subscription_ids',
        help_text='Contacto (Odoo contact_id).',
    )
    mailing_list = fields.Many2one(
        MailingList, on_delete=models.CASCADE,
        related_name='subscription_ids',
        help_text='Lista (Odoo list_id).',
    )
    opt_out = fields.Boolean(
        default=False,
        help_text='El contacto se dio de baja de ESTA lista (Odoo opt_out).',
    )
    opt_out_datetime = fields.Datetime(
        null=True, blank=True,
        help_text='Momento del opt-out (Odoo opt_out_datetime).',
    )

    class Meta:
        db_table = 'mailing_subscription'
        ordering = ['-created_at', '-id']
        verbose_name = 'Suscripcion a lista de correo'
        verbose_name_plural = 'Suscripciones a listas de correo'
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'mailing_list'],
                name='unique_mailing_subscription',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.contact_id}→{self.mailing_list_id} (opt_out={self.opt_out})'
