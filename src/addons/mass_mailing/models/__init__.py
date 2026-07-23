"""Modelos del addon ``mass_mailing`` — paquete espejo de
``odoo/addons/mass_mailing/models/`` (un archivo por modelo Odoo).

Hogar fiel de la newsletter (addon de proyecto ``newsletter``, en disolucion):

- ``mailing_list.py`` → ``MailingList`` (``mailing.list``).
- ``mailing_contact.py`` → ``MailingContact`` (``mailing.contact``).
- ``mailing_subscription.py`` → ``MailingSubscription`` (``mailing.subscription``).
- ``mailing_mailing.py`` → ``MailingMailing`` (``mailing.mailing``; hereda ``mail.thread``).
- ``mailing_trace.py`` → ``MailingTrace`` (``mailing.trace``, entrega por destinatario).
"""
from .mailing_list import MailingList
from .mailing_contact import MailingContact
from .mailing_subscription import MailingSubscription
from .mailing_mailing import MailingMailing
from .mailing_trace import MailingTrace

__all__ = [
    'MailingList', 'MailingContact', 'MailingSubscription',
    'MailingMailing', 'MailingTrace',
]
