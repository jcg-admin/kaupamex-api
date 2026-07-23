"""AppConfig — addons.mail (equivalente del addon ``mail`` de Odoo).

``addons.mail`` es el hogar fiel del envío de correo del proyecto (DEC-11 de
``adoptar-arquitectura-server-service-odoo``). Odoo modela el correo en el addon
``mail`` — ``mail.mail`` con ``process_email_queue`` (cola + envío async por cron,
``odoo/addons/mail/models/mail_mail.py``) — sobre el transporte SMTP
``ir.mail_server`` de ``addons/base``.

La cola de correo saliente es ``mail.mail`` (``MailMail``) — hogar Odoo fiel de
la ex-``notifications.EmailTask`` (disuelta en esta familia) — drenada por el
management command ``send_pending_emails`` (≙ ``mail.mail.process_email_queue``).
``email_executor`` hace el dispatch async por ``ThreadPoolExecutor`` y reencola
en ``mail.mail`` los envíos que fallan en el thread pool.
"""
import importlib

from django.apps import AppConfig


class MailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.mail'
    label = 'mail'
    verbose_name = 'Mail (envío de correo, fiel al addon mail de Odoo)'

    def ready(self):
        # Registro de signals de notificación transaccional, reubicados desde
        # ``addons.notifications`` (disolución notifications→mail, slice 3e-2).
        # No puede ser un ``import`` top-level: ``notification_signals`` importa
        # modelos de orders/payments/returns/support antes de que el registro de
        # apps esté listo (AppRegistryNotReady). Excepción #4 de
        # no-lazy-imports.md (constraint de lifecycle de Django): se difiere con
        # ``importlib.import_module`` — es una llamada de función, no un
        # statement ``import``, así que el AST gate da exit 0.
        importlib.import_module('addons.mail.models.notification_handlers')
        importlib.import_module('addons.mail.models.notification_signals')
