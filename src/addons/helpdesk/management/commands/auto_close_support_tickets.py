"""
auto_close_support_tickets — envoltura de CLI sobre ``SupportTicket.auto_close_stale``.

El cierre por inactividad lo corre el **cron** ``ir_cron_helpdesk_auto_close``.
La lógica vive en el modelo —``addons.helpdesk.models.SupportTicket.
auto_close_stale``— porque ``ir.cron`` invoca ``<model>.<method>()`` y no sabe
ejecutar comandos de Django.

Este comando se conserva como **entrada manual**: forzar el barrido una vez sin
esperar al ciclo del cron. No duplica la lógica; la invoca.

    python manage.py auto_close_support_tickets
    python manage.py auto_close_support_tickets --dias 14
"""
from django.core.management.base import BaseCommand

from addons.helpdesk.models import SupportTicket
from addons.helpdesk.models.support_ticket import AUTO_CLOSE_DAYS


class Command(BaseCommand):
    help = (
        f'Cierra tickets AWAITING_USER sin actividad por {AUTO_CLOSE_DAYS} '
        f'dias y notifica al usuario (UC-NOT-08). El ciclo normal lo corre el '
        f'cron ir_cron_helpdesk_auto_close; esto es la entrada manual.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=AUTO_CLOSE_DAYS,
            help=f'Dias de inactividad antes de cerrar (default {AUTO_CLOSE_DAYS}).',
        )

    def handle(self, *args, **options):
        cerrados, fallidos = SupportTicket.auto_close_stale(dias=options['dias'])
        self.stdout.write(
            self.style.SUCCESS(
                f'auto_close_support_tickets: closed={cerrados} failed={fallidos}'
            )
        )
