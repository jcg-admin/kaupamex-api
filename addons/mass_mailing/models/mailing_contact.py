"""``mailing.contact`` — contacto de envio masivo (Odoo ``mass_mailing``).

Portacion fiel de ``mass_mailing/models/mailing_contact.py`` (``mailing.contact``,
Odoo 19 community, LGPL-3): el destinatario de una campana masiva. Es el hogar
Odoo del ``NewsletterSubscriber`` del addon de proyecto ``newsletter`` (disuelto):
un contacto puede ser anonimo (solo-email), no necesariamente un usuario.

El ``mail.thread.blacklist`` de Odoo (que aporta ``is_blacklisted`` +
``message_bounce``) se reduce aqui a los dos campos escalares que este stack
necesita; la lista negra global (``mail.blacklist``) se porta en un paso
posterior si un flujo la requiere (Clausula 5 — no se fabrica antes de uso).
"""
import fields
import models

from addons.base.models import TimeStampedModel


class MailingContact(TimeStampedModel):
    """``mailing.contact`` — destinatario de campanas masivas."""

    name = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Nombre completo (Odoo name).',
    )
    company_name = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Empresa (Odoo company_name).',
    )
    email = fields.Char(
        max_length=254, blank=True, default='',
        help_text='Correo (Odoo email).',
    )
    country_id = fields.Many2one(
        'base.ResCountry', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='mailing_contacts', help_text='Pais (Odoo country_id).',
        db_column='country_id',
    )
    # De mail.thread.blacklist (Odoo): contador de rebotes + bandera de lista negra.
    message_bounce = fields.Integer(
        default=0, help_text='Rebotes acumulados (Odoo message_bounce).',
    )
    is_blacklisted = fields.Boolean(
        default=False,
        help_text='En lista negra global de correo (Odoo is_blacklisted).',
    )

    class Meta:
        db_table = 'mailing_contact'
        ordering = ['-created_at', '-id']
        verbose_name = 'Contacto de envio masivo'
        verbose_name_plural = 'Contactos de envio masivo'
        indexes = [
            models.Index(fields=['email']),
        ]

    def __str__(self) -> str:
        return self.name or self.email or f'Contact#{self.pk}'
