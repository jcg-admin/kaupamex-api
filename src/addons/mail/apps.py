"""AppConfig — addons.mail (equivalente del addon ``mail`` de Odoo).

``addons.mail`` es el hogar fiel del envío de correo del proyecto (DEC-11 de
``adoptar-arquitectura-server-service-odoo``). Odoo modela el correo en el addon
``mail`` — ``mail.mail`` con ``process_email_queue`` (cola + envío async por cron,
``odoo/addons/mail/models/mail_mail.py``) — sobre el transporte SMTP
``ir.mail_server`` de ``addons/base``.

Primer inquilino: ``email_executor`` (dispatch async por ``ThreadPoolExecutor`` +
cola de reintento; ≙ ``mail.mail.process_email_queue``). La cola de reintento
``EmailTask`` vive hoy en ``addons.notifications`` y migrará aquí cuando
``notifications`` se disuelva en ``mail`` (Odoo: ``mail.message``/``mail.mail``).
"""
from django.apps import AppConfig


class MailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.mail'
    label = 'mail'
    verbose_name = 'Mail (envío de correo, fiel al addon mail de Odoo)'
