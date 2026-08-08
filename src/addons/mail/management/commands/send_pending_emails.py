"""
send_pending_emails — envoltura de CLI sobre ``MailMail.process_email_queue``.

La cola de correo saliente la procesa el **cron** ``ir_cron_mail_scheduler``,
igual que en la referencia (``odoo19c: mail/data/ir_cron_data.xml:4-13``, cuyo
cuerpo es ``model.process_email_queue(batch_size=1000)``). La lógica vive en el
modelo — ``addons.mail.models.MailMail.process_email_queue`` — porque ``ir.cron``
invoca ``<model>.<method>()`` y no sabe ejecutar comandos de Django.

Este comando se conserva como **entrada manual**: correr la cola una vez sin
esperar al ciclo del cron (depuración, o desagüe tras una caída de SMTP). No
duplica la lógica; la invoca.

    python manage.py send_pending_emails
    python manage.py send_pending_emails --batch-size 500
"""
from django.core.management.base import BaseCommand

from addons.mail.models import MailMail


class Command(BaseCommand):
    help = (
        'Procesa la cola de correo saliente una vez. El ciclo normal lo corre '
        'el cron ir_cron_mail_scheduler; esto es la entrada manual.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size', type=int, default=None,
            help='Correos por corrida. Por defecto, el del método (50).',
        )

    def handle(self, *args, **options):
        tamano = options.get('batch_size')
        if tamano is None:
            sent, failed, skipped = MailMail.process_email_queue()
        else:
            sent, failed, skipped = MailMail.process_email_queue(batch_size=tamano)

        self.stdout.write(
            self.style.SUCCESS(
                f'send_pending_emails: sent={sent} failed={failed} '
                f'skipped={skipped}'
            )
        )
