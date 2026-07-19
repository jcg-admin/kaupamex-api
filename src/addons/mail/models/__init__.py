"""Modelos del addon ``mail`` — paquete espejo de ``odoo/addons/mail/models/``.

Un archivo por modelo Odoo (monolito modular, como Odoo). Backbone del chatter:

- ``mail_message_subtype.py`` → ``MailMessageSubtype`` (``mail.message.subtype``).
- ``mail_message.py`` → ``MailMessage`` (``mail.message``, mensaje polimorfico).
- ``mail_followers.py`` → ``MailFollowers`` (``mail.followers``, seguidores).
- ``mail_thread.py`` → ``MailThread`` (``mail.thread``, mixin abstracto que dota
  a cualquier modelo de ``message_post``/``message_subscribe``).

El envío de correo de Odoo vive en ``models/mail_mail.py`` (``mail.mail`` con
``process_email_queue``). Aquí reside el servicio de envío async ``email_executor``
(≙ ``mail.mail.process_email_queue``) como módulo de la capa de modelos.

No se importa ``email_executor`` en este ``__init__`` a propósito: importa
``EmailTask`` de ``addons.notifications`` y no debe cargarse al poblar el
registro de apps. Los consumidores importan la ruta completa
``addons.mail.models.email_executor``. Los modelos del backbone NO importan
``notifications`` — son seguros de reexportar aquí.
"""
from .mail_message_subtype import MailMessageSubtype
from .mail_message import MailMessage
from .mail_followers import MailFollowers
from .mail_thread import MailThread

__all__ = ['MailMessageSubtype', 'MailMessage', 'MailFollowers', 'MailThread']
