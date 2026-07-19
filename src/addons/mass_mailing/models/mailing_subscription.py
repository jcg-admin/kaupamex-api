"""``mailing.subscription`` — membresia contacto↔lista (Odoo ``mass_mailing``).

Portacion fiel de ``mass_mailing/models/mailing_subscription.py``
(``mailing.subscription``, antes ``mailing.contact.subscription``): la tabla
intermedia con datos del M2M ``mailing.contact`` ↔ ``mailing.list``. El opt-out
es **por lista** (un contacto puede seguir una lista y salirse de otra), fiel a
Odoo — a diferencia del opt-out global del ``NewsletterSubscriber`` de proyecto.
"""
import secrets

from django.core import signing
from django.utils import timezone

import fields
import models

from addons.base.models import TimeStampedModel

from .mailing_contact import MailingContact
from .mailing_list import MailingList


def _generate_unsubscribe_token():
    """Token HMAC firmado para el enlace de baja (DEC-NEW-02, heredado del
    addon ``newsletter`` en disolucion). En Odoo el token de baja es un HMAC
    **computado** al vuelo (``_generate_mailing_recipient_token``); este stack
    lo **almacena** (adaptacion de proyecto, preservada al disolver)."""
    return signing.dumps(secrets.token_urlsafe(16), salt='mailing-unsub')


class MailingSubscription(TimeStampedModel):
    """``mailing.subscription`` — contacto suscrito a una lista, con opt-out.

    Aloja tambien el **doble opt-in por lista** que traia el ``newsletter`` de
    proyecto (DEC-NEW-02): ``confirmed_at`` nulo = pendiente de confirmar,
    seteado = confirmado; ``opt_out`` = dado de baja. Mas fiel que el opt-out
    global del ``NewsletterSubscriber`` — en Odoo la suscripcion es por lista.
    """

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
    # Doble opt-in (adaptacion de proyecto DEC-NEW-02, ex-``newsletter``).
    confirmed_at = fields.Datetime(
        null=True, blank=True,
        help_text='Momento de la confirmacion (nulo = pendiente doble opt-in).',
    )
    confirmation_token = fields.Char(
        max_length=200, null=True, blank=True, default=None,
        help_text='Token del enlace de confirmacion (doble opt-in).',
    )
    unsubscribe_token = fields.Char(
        max_length=200, unique=True, default=_generate_unsubscribe_token,
        help_text='Token del enlace de baja (Odoo lo computa; aqui se almacena).',
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

    @property
    def is_pending(self) -> bool:
        """Alta sin confirmar (doble opt-in pendiente) y no dada de baja."""
        return self.confirmed_at is None and not self.opt_out

    @property
    def is_confirmed(self) -> bool:
        """Confirmada y activa (recibe envios)."""
        return self.confirmed_at is not None and not self.opt_out

    def confirm(self):
        """Confirma el doble opt-in (Odoo: opt-in de la suscripcion)."""
        self.confirmed_at = timezone.now()
        self.opt_out = False
        self.opt_out_datetime = None
        self.confirmation_token = None
        self.save(update_fields=[
            'confirmed_at', 'opt_out', 'opt_out_datetime',
            'confirmation_token', 'updated_at',
        ])

    def unsubscribe(self):
        """Baja de ESTA lista (Odoo ``opt_out=True`` en la suscripcion)."""
        self.opt_out = True
        self.opt_out_datetime = timezone.now()
        self.save(update_fields=['opt_out', 'opt_out_datetime', 'updated_at'])
