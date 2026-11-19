"""AppConfig — addons.mail (equivalente del addon ``mail`` de Odoo).

``addons.mail`` es el hogar fiel del envío de correo del proyecto (DEC-11 de
``adoptar-arquitectura-server-service-odoo``). Odoo modela el correo en el
addon
``mail`` — ``mail.mail`` con ``process_email_queue`` (cola + envío async por
cron,
``odoo/addons/mail/models/mail_mail.py``) — sobre el transporte SMTP
``ir.mail_server`` de ``addons/base``.

La cola de correo saliente es ``mail.mail`` (``MailMail``) — hogar Odoo fiel de
la ex-``notifications.EmailTask`` (disuelta en esta familia) — drenada por el
management command ``send_pending_emails`` (≙
``mail.mail.process_email_queue``).
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
        # Cuelga lo que ``mail`` extiende en ResCompany (el dominio de alias,
        # sus direcciones y los colores de correo) — ≙
        # ``mail/models/res_company.py``. ``importlib.import_module`` es la
        # excepción #4 sancionada para ``ready()``.
        importlib.import_module(
            f'{self.name}.models.res_company'
        ).apply_mail_company_extensions()
        # ≙ ``mail/models/ir_mail_server.py``: los campos de dueño y las
        # sobreescrituras de ``ir.mail_server``.
        importlib.import_module(
            f'{self.name}.models.ir_mail_server'
        ).apply_mail_server_extensions()
