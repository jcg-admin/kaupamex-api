"""Modelos del addon ``mail`` — paquete espejo de ``odoo/addons/mail/models/``.

Un archivo por modelo Odoo (monolito modular, como Odoo). Backbone del chatter:

- ``mail_message_subtype.py`` → ``MailMessageSubtype`` (``mail.message.subtype``).
- ``mail_message.py`` → ``MailMessage`` (``mail.message``, mensaje polimorfico).
- ``mail_followers.py`` → ``MailFollowers`` (``mail.followers``, seguidores).
- ``mail_thread.py`` → ``MailThread`` (``mail.thread``, mixin abstracto que dota
  a cualquier modelo de ``message_post``/``message_subscribe``).

El correo saliente de Odoo vive en ``models/mail_mail.py`` (``mail.mail``, la
cola encolada + envío async por ``process_email_queue``; hogar fiel de la
ex-``notifications.EmailTask``). El servicio de dispatch async ``email_executor``
(≙ ``mail.mail.process_email_queue``) reside aquí como módulo de la capa de
modelos y ya solo depende de ``mail`` (``MailMail``), no de ``notifications``.

``email_executor`` no se reexporta en este ``__init__`` a propósito: es un módulo
de servicio con estado (un ``ThreadPoolExecutor``), no un modelo. Los
consumidores importan la ruta completa ``addons.mail.models.email_executor``.
"""
from .mail_alias import MailAlias, DOT_ATOM_TEXT
from .mail_alias_domain import MailAliasDomain
from .mail_message_subtype import MailMessageSubtype
from .mail_message import MailMessage
from .mail_followers import MailFollowers
from .mail_notification import MailNotification
from .mail_activity_type import MailActivityType
from .mail_activity import MailActivity
from .mail_activity_mixin import MailActivityMixin
from .mail_tracking_value import MailTrackingValue
from .mail_template import MailTemplate
from .mail_mail import MailMail
from .notification_inbox import (
    Notification,
    NotificationType,
    NOTIFICATION_TYPE_LABELS,
    MANDATORY_NOTIFICATION_TYPES,
)
from .notification_preference import NotificationPreference
from .manual_notification import ManualNotification
from .mail_thread import MailThread

__all__ = [
    'MailAlias', 'MailAliasDomain', 'DOT_ATOM_TEXT',
    'MailMessageSubtype', 'MailMessage', 'MailFollowers', 'MailNotification',
    'MailActivityType', 'MailActivity', 'MailActivityMixin',
    'MailTrackingValue',
    'MailTemplate', 'MailMail', 'MailThread',
    'Notification', 'NotificationType', 'NOTIFICATION_TYPE_LABELS',
    'MANDATORY_NOTIFICATION_TYPES', 'NotificationPreference',
    'ManualNotification',
]
